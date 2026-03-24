from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dspy
import polars as pl


class GenerateTransform(dspy.Signature):
    """Generate a small Python transform function for a CSV dataset.

    The function must use Polars, accept a `pl.DataFrame` named `df`, and return a `pl.DataFrame`.
    Prefer deterministic code with no network/file writes.
    """

    headers: str = dspy.InputField(desc="CSV headers, comma separated")
    prompt: str = dspy.InputField(desc="User request describing the desired data processing")
    transform_name: str = dspy.OutputField(desc="snake_case short transform name")
    python_code: str = dspy.OutputField(desc="Python code that defines `transform(df: pl.DataFrame) -> pl.DataFrame`")
    reasoning: str = dspy.OutputField(desc="Short explanation of what the code does")
    output_mode: str = dspy.OutputField(desc="csv or preview")


class RuleBasedCodegenLM(dspy.BaseLM):
    """A tiny deterministic LM used for local verification without external model credentials.

    It emits DSPy ChatAdapter-formatted fields so the flow still uses DSPy primitives.
    """

    def __init__(self) -> None:
        super().__init__(model="rulebased-dspy", model_type="chat")

    def forward(self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None, **kwargs):
        text = next((m.get("content", "") for m in reversed(messages or []) if m.get("role") == "user"), prompt or "")
        headers = _extract_field(text, "headers")
        user_prompt = _extract_field(text, "prompt")
        payload = _build_codegen_payload(headers=headers, prompt=user_prompt)
        content = "\n\n".join(
            [
                "[[ ## transform_name ## ]]\n" + payload["transform_name"],
                "[[ ## python_code ## ]]\n" + payload["python_code"],
                "[[ ## reasoning ## ]]\n" + payload["reasoning"],
                "[[ ## output_mode ## ]]\n" + payload["output_mode"],
                "[[ ## completed ## ]]",
            ]
        )
        return _fake_openai_response(content, self.model)


@dataclass
class PipelineResult:
    run_dir: Path
    metadata_path: Path
    code_path: Path
    preview_path: Path
    result_path: Path | None
    prompt_path: Path
    source_csv: Path


class CsvPromptPipeline(dspy.Module):
    def __init__(self, predictor: dspy.Predict | None = None):
        super().__init__()
        self.predictor = predictor or dspy.Predict(GenerateTransform)

    def forward(self, csv_path: str | Path, prompt: str, output_dir: str | Path = "runs") -> PipelineResult:
        csv_path = Path(csv_path).resolve()
        run_dir = _make_run_dir(Path(output_dir).resolve())
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")

        headers = pl.read_csv(csv_path, n_rows=0).columns
        prediction = self.predictor(headers=", ".join(headers), prompt=prompt)

        normalized_code = textwrap.dedent(prediction.python_code).strip() + "\n"
        code_path = run_dir / f"{prediction.transform_name}.py"
        code_path.write_text(normalized_code, encoding="utf-8")

        df = pl.read_csv(csv_path)
        result_df, sandbox_meta = execute_generated_transform(normalized_code, df)

        preview_path = run_dir / "result_preview.json"
        preview = {
            "columns": result_df.columns,
            "shape": list(result_df.shape),
            "rows": result_df.head(20).to_dicts(),
        }
        preview_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")

        result_path = None
        output_mode = prediction.output_mode.strip().lower()
        estimated_bytes = len(result_df.write_csv().encode("utf-8")) if result_df.height or result_df.width else 0
        if output_mode == "csv" or estimated_bytes > 4000 or result_df.height > 20:
            result_path = run_dir / "result.csv"
            result_df.write_csv(result_path)

        metadata = {
            "generated_at": datetime.now().isoformat(),
            "source_csv": str(csv_path),
            "prompt_path": str(prompt_path),
            "prompt": prompt,
            "input_headers": headers,
            "generated_code_path": str(code_path),
            "reasoning": prediction.reasoning,
            "output_mode": prediction.output_mode,
            "sandbox": sandbox_meta,
            "result": {
                "shape": list(result_df.shape),
                "columns": result_df.columns,
                "preview_path": str(preview_path),
                "result_path": str(result_path) if result_path else None,
            },
        }
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return PipelineResult(
            run_dir=run_dir,
            metadata_path=metadata_path,
            code_path=code_path,
            preview_path=preview_path,
            result_path=result_path,
            prompt_path=prompt_path,
            source_csv=csv_path,
        )


def execute_generated_transform(code: str, df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    code = textwrap.dedent(code).strip()

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "polars":
            return pl
        raise ImportError(f"Import '{name}' is not allowed in the sandbox")

    safe_builtins = {
        "__import__": restricted_import,
        "len": len,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "list": list,
        "dict": dict,
        "set": set,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "abs": abs,
        "round": round,
        "print": print,
    }
    globals_dict = {
        "__builtins__": safe_builtins,
        "pl": pl,
    }
    locals_dict: dict[str, Any] = {}
    exec(code, globals_dict, locals_dict)
    transform = locals_dict.get("transform") or globals_dict.get("transform")
    if not callable(transform):
        raise ValueError("Generated code did not define a callable transform(df)")
    result = transform(df.clone())
    if not isinstance(result, pl.DataFrame):
        raise TypeError("Generated transform must return a polars.DataFrame")
    return result, {
        "executor": "python_exec_with_restricted_builtins",
        "available_globals": ["pl"],
        "code_sha1": _sha1_text(code),
    }


def build_pipeline(use_real_lm: bool = False) -> CsvPromptPipeline:
    if use_real_lm:
        model = os.getenv("DSPY_MODEL")
        if not model:
            raise ValueError("DSPY_MODEL is required when --real-lm is used")
        dspy.configure(lm=dspy.LM(model=model))
    else:
        dspy.configure(lm=RuleBasedCodegenLM())
    return CsvPromptPipeline()


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DSPy CSV prompt runner")
    parser.add_argument("--csv", required=True, help="Path to input CSV")
    parser.add_argument("--prompt", help="Inline prompt")
    parser.add_argument("--prompt-file", help="Path to prompt txt file")
    parser.add_argument("--output-dir", default="runs", help="Directory for run artifacts")
    parser.add_argument("--real-lm", action="store_true", help="Use DSPY_MODEL-backed LM instead of local rule-based LM")
    args = parser.parse_args(argv)

    if not args.prompt and not args.prompt_file:
        parser.error("one of --prompt or --prompt-file is required")
    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")

    pipeline = build_pipeline(use_real_lm=args.real_lm)
    result = pipeline(csv_path=args.csv, prompt=prompt, output_dir=args.output_dir)

    summary = {
        "run_dir": str(result.run_dir),
        "metadata": str(result.metadata_path),
        "generated_code": str(result.code_path),
        "preview": str(result.preview_path),
        "result_file": str(result.result_path) if result.result_path else None,
        "prompt_file": str(result.prompt_path),
        "source_csv": str(result.source_csv),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _extract_field(text: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^\s*\[\[ ## {re.escape(field_name)} ## \]\]\s*\n(.*?)(?=^\s*\[\[ ##|\Z)",
        re.S | re.M,
    )
    matches = list(pattern.finditer(text))
    return matches[-1].group(1).strip() if matches else ""


def _build_codegen_payload(headers: str, prompt: str) -> dict[str, str]:
    header_list = [h.strip() for h in headers.split(",") if h.strip()]
    lower_prompt = prompt.lower()

    group_col = _pick_column(header_list, ["city", "category", "group", "region", "name"])
    sum_col = _pick_column(header_list, ["sales", "amount", "revenue", "total", "price"])
    upper_col = _pick_column(header_list, ["name", "city", "category"])

    if any(key in lower_prompt for key in ["sum", "total", "aggregate", "group by", "groupby"]):
        transform_name = f"aggregate_{group_col or 'data'}_{sum_col or 'rows'}"
        if group_col and sum_col:
            code = f'''import polars as pl\n\ndef transform(df: pl.DataFrame) -> pl.DataFrame:\n    return (\n        df.group_by("{group_col}")\n        .agg(pl.col("{sum_col}").sum().alias("total_{sum_col}"))\n        .sort("{group_col}")\n    )\n'''
            reasoning = f"Group by `{group_col}` and sum `{sum_col}`."
        else:
            code = """import polars as pl\n\ndef transform(df: pl.DataFrame) -> pl.DataFrame:\n    return df\n"""
            reasoning = "Could not infer a grouping and numeric column safely, so the original data is returned."
        return {
            "transform_name": transform_name,
            "python_code": code.strip(),
            "reasoning": reasoning,
            "output_mode": "csv",
        }

    if any(key in lower_prompt for key in ["uppercase", "upper case", "大写"]):
        target = upper_col or (header_list[0] if header_list else "value")
        code = f'''def transform(df: pl.DataFrame) -> pl.DataFrame:\n    return df.with_columns(pl.col("{target}").cast(pl.Utf8).str.to_uppercase().alias("{target}_upper"))\n'''
        return {
            "transform_name": f"uppercase_{target}",
            "python_code": code.strip(),
            "reasoning": f"Create an uppercase helper column from `{target}`.",
            "output_mode": "preview",
        }

    if any(key in lower_prompt for key in ["filter", "大于", ">"]):
        threshold = _extract_number(lower_prompt) or 0
        numeric = sum_col or _pick_column(header_list, ["score", "qty", "count", "age"])
        if numeric:
            code = f'''import polars as pl\n\ndef transform(df: pl.DataFrame) -> pl.DataFrame:\n    return df.filter(pl.col("{numeric}") > {threshold})\n'''
            reasoning = f"Filter rows where `{numeric}` > {threshold}."
        else:
            code = """import polars as pl\n\ndef transform(df: pl.DataFrame) -> pl.DataFrame:\n    return df\n"""
            reasoning = "No numeric-like column was inferred, so the original data is returned."
        return {
            "transform_name": f"filter_{numeric or 'rows'}",
            "python_code": code.strip(),
            "reasoning": reasoning,
            "output_mode": "csv",
        }

    code = """import polars as pl\n\ndef transform(df: pl.DataFrame) -> pl.DataFrame:\n    return df\n"""
    return {
        "transform_name": "identity_transform",
        "python_code": code.strip(),
        "reasoning": "Fallback transform: return the original dataframe unchanged.",
        "output_mode": "preview",
    }


def _pick_column(headers: list[str], candidates: list[str]) -> str | None:
    lowered = {h.lower(): h for h in headers}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    for header in headers:
        low = header.lower()
        if any(candidate in low for candidate in candidates):
            return header
    return None


def _extract_number(text: str) -> int | None:
    match = re.search(r"(-?\d+)", text)
    return int(match.group(1)) if match else None


def _make_run_dir(root: Path) -> Path:
    run_dir = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _sha1_text(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _fake_openai_response(content: str, model: str):
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)
