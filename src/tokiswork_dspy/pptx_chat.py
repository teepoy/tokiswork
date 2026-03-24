"""Model-driven natural-language chat entry for PPTX workflows.

Primary path: DSPy planning / parameter extraction.
Fallback path: deterministic rule-based parsing so local tests remain stable.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import dspy

from .pptx_core import analyze_template, create_template_from_spec, run_pptx_agent

_PATH_RE = re.compile(r"(?:[\w./~\\-]+\.pptx)")
_QUOTED_PATH_RE = re.compile(r'(["\'])(.+?\.pptx)\1')
_FIELD_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class PPTXChatRequest:
    operation: str = "fill"
    template_path: str | None = None
    output_path: str | None = None
    output_dir: str = "pptx_runs"
    user_input: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    raw_chat: str = ""
    parser_mode: str = "dspy"
    planner_reasoning: str = ""
    planner_confidence: str = ""


class PlanPPTXChatRequest(dspy.Signature):
    """Turn a free-form PPTX chat request into a structured execution plan."""

    chat_text: str = dspy.InputField(desc="User request about PPTX analyze/create/fill work")
    operation: str = dspy.OutputField(desc="One of: analyze, create, fill")
    template_path: str = dspy.OutputField(desc="Input template .pptx path if present, otherwise empty")
    output_path: str = dspy.OutputField(desc="Output .pptx path if requested, otherwise empty")
    output_dir: str = dspy.OutputField(desc="Output directory if mentioned, otherwise pptx_runs")
    fields_json: str = dspy.OutputField(desc="JSON object of template fields for create mode, else {}")
    content: str = dspy.OutputField(desc="Normalized business content/instructions to pass into the fill agent")
    confidence: str = dspy.OutputField(desc="high, medium, or low")
    reasoning: str = dspy.OutputField(desc="Short explanation of planning decisions")


class RuleBasedPPTXChatLM(dspy.BaseLM):
    """Deterministic local LM for chat planning.

    It still speaks in DSPy ChatAdapter blocks so the primary control flow is model-driven,
    but without requiring external credentials for tests/examples.
    """

    def __init__(self) -> None:
        super().__init__(model="rulebased-pptx-chat", model_type="chat")

    def forward(
        self,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **kwargs,
    ):
        chat_text = next(
            (m.get("content", "") for m in reversed(messages or []) if m.get("role") == "user"),
            prompt or "",
        )
        plan = _build_rulebased_plan(chat_text)
        content = "\n\n".join(
            [
                f"[[ ## operation ## ]]\n{plan['operation']}",
                f"[[ ## template_path ## ]]\n{plan['template_path']}",
                f"[[ ## output_path ## ]]\n{plan['output_path']}",
                f"[[ ## output_dir ## ]]\n{plan['output_dir']}",
                f"[[ ## fields_json ## ]]\n{json.dumps(plan['fields'], ensure_ascii=False)}",
                f"[[ ## content ## ]]\n{plan['content']}",
                f"[[ ## confidence ## ]]\n{plan['confidence']}",
                f"[[ ## reasoning ## ]]\n{plan['reasoning']}",
                "[[ ## completed ## ]]",
            ]
        )
        return _fake_openai_response(content, self.model)


def _extract_paths(chat_text: str) -> list[str]:
    paths: list[str] = []
    for match in _QUOTED_PATH_RE.finditer(chat_text):
        paths.append(match.group(2))
    for match in _PATH_RE.finditer(chat_text):
        candidate = match.group(0)
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _infer_operation(chat_text: str) -> str:
    text = chat_text.lower()
    if any(k in text for k in ["analyze", "inspect", "查看模板", "分析模板", "模板里有哪些字段"]):
        return "analyze"
    if any(k in text for k in ["create template", "make template", "新建模板", "创建模板", "生成模板"]):
        return "create"
    return "fill"


def _extract_output_dir(chat_text: str) -> str:
    patterns = [
        r'output dir(?:ectory)?\s*(?:is|=|to)?\s*["\']?([^"\'\n]+)["\']?',
        r'输出目录(?:是|为)?\s*["\']?([^"\'\n]+)["\']?',
    ]
    for pattern in patterns:
        match = re.search(pattern, chat_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "pptx_runs"


def _extract_output_path(chat_text: str) -> str | None:
    path_capture = r'([^"\'\s，。,；;\n]+\.pptx)'
    patterns = [
        rf'save (?:it )?(?:as|to)\s*["\']?{path_capture}["\']?',
        rf'\boutput(?: path)?\b\s*(?:is|=|to)?\s*["\']?{path_capture}["\']?',
        rf'输出(?:路径|文件)?(?:是|为|到)?\s*["\']?{path_capture}["\']?',
        rf'保存到\s*["\']?{path_capture}["\']?',
        rf'生成到\s*["\']?{path_capture}["\']?',
        rf'创建到\s*["\']?{path_capture}["\']?',
    ]
    for pattern in patterns:
        match = re.search(pattern, chat_text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("。.,，")
    return None


def _extract_fields_spec(chat_text: str) -> dict[str, str]:
    quoted_json = _FIELD_BLOCK_RE.search(chat_text)
    if quoted_json:
        try:
            data = json.loads(quoted_json.group(0))
            return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass

    match = re.search(r"fields?\s*[:：]\s*(.+)", chat_text, re.IGNORECASE)
    if not match:
        match = re.search(r"字段\s*[:：]\s*(.+)", chat_text)
    if not match:
        return {}

    fields_text = match.group(1).strip()
    names = [
        token.strip(" `，,。;；")
        for token in re.split(r"[,，]\s*", fields_text)
        if token.strip(" `，,。;；")
    ]
    return {name: name for name in names}


def _strip_detected_paths(text: str, *paths: str | None) -> str:
    cleaned = text
    for path in paths:
        if path:
            cleaned = cleaned.replace(path, " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_content(chat_text: str, template_path: str | None, output_path: str | None) -> str:
    content_patterns = [
        r"内容(?:是|为)?[:：]\s*(.+)",
        r"根据以下内容(?:生成|填充)?[:：]\s*(.+)",
        r"fill .*? with[:：]?\s*(.+)",
        r"using .*? content[:：]?\s*(.+)",
    ]
    for pattern in content_patterns:
        match = re.search(pattern, chat_text, re.IGNORECASE | re.DOTALL)
        if match:
            return _strip_detected_paths(match.group(1).strip(), template_path, output_path)
    return _strip_detected_paths(chat_text.strip(), template_path, output_path)


def _build_rulebased_plan(chat_text: str) -> dict[str, Any]:
    paths = _extract_paths(chat_text)
    operation = _infer_operation(chat_text)
    template_path = paths[0] if paths else None
    output_path = _extract_output_path(chat_text)

    if operation == "fill" and len(paths) > 1 and not output_path:
        output_path = paths[1]
    if operation == "create" and paths:
        output_path = output_path or paths[0]
        template_path = None

    fields = _extract_fields_spec(chat_text)
    content = _extract_content(chat_text, template_path, output_path)
    confidence = "high" if (operation != "fill" or template_path) else "medium"

    return {
        "operation": operation,
        "template_path": template_path or "",
        "output_path": output_path or "",
        "output_dir": _extract_output_dir(chat_text),
        "fields": fields,
        "content": content,
        "confidence": confidence,
        "reasoning": "Deterministic fallback planner based on path/keyword/field heuristics.",
    }


def _extract_field(text: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^\s*\[\[ ## {re.escape(field_name)} ## \]\]\s*\n(.*?)(?=^\s*\[\[ ##|\Z)",
        re.S | re.M,
    )
    matches = list(pattern.finditer(text))
    return matches[-1].group(1).strip() if matches else ""


def _fake_openai_response(content: str, model: str):
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _safe_json_dict(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _sanitize_pptx_path(value: str) -> str:
    candidate = (value or "").strip().strip('"\'').rstrip("。.,，；;")
    if candidate.endswith(".pptx"):
        return candidate
    paths = _extract_paths(candidate)
    return paths[0] if paths else ""


def _normalize_plan(plan: dict[str, str], raw_chat: str, parser_mode: str) -> PPTXChatRequest:
    operation = (plan.get("operation") or "fill").strip().lower()
    if operation not in {"analyze", "create", "fill"}:
        operation = _infer_operation(raw_chat)

    template_path = _sanitize_pptx_path(plan.get("template_path") or "") or None
    output_path = _sanitize_pptx_path(plan.get("output_path") or "") or None
    output_dir = (plan.get("output_dir") or "pptx_runs").strip() or "pptx_runs"
    fields = _safe_json_dict(plan.get("fields_json", "{}"))

    if operation == "create" and not output_path:
        fallback = _build_rulebased_plan(raw_chat)
        output_path = fallback["output_path"] or None
        if not fields:
            fields = fallback["fields"]

    if operation == "fill" and not template_path:
        fallback = _build_rulebased_plan(raw_chat)
        template_path = fallback["template_path"] or None
        output_path = output_path or (fallback["output_path"] or None)

    if operation == "analyze" and not template_path:
        fallback = _build_rulebased_plan(raw_chat)
        template_path = fallback["template_path"] or None

    content = (plan.get("content") or "").strip()
    if not content:
        content = _extract_content(raw_chat, template_path, output_path)

    return PPTXChatRequest(
        operation=operation,
        template_path=template_path,
        output_path=output_path,
        output_dir=output_dir,
        user_input=content,
        fields=fields,
        raw_chat=raw_chat,
        parser_mode=parser_mode,
        planner_reasoning=(plan.get("reasoning") or "").strip(),
        planner_confidence=(plan.get("confidence") or "").strip(),
    )


def _parse_with_predictor(chat_text: str, lm: dspy.BaseLM, parser_mode: str) -> PPTXChatRequest:
    predictor = dspy.Predict(PlanPPTXChatRequest)
    with dspy.context(lm=lm):
        prediction = predictor(chat_text=chat_text)
    plan = {
        "operation": getattr(prediction, "operation", ""),
        "template_path": getattr(prediction, "template_path", ""),
        "output_path": getattr(prediction, "output_path", ""),
        "output_dir": getattr(prediction, "output_dir", ""),
        "fields_json": getattr(prediction, "fields_json", "{}"),
        "content": getattr(prediction, "content", ""),
        "confidence": getattr(prediction, "confidence", ""),
        "reasoning": getattr(prediction, "reasoning", ""),
    }
    return _normalize_plan(plan, raw_chat=chat_text, parser_mode=parser_mode)


def parse_chat_request(chat_text: str) -> PPTXChatRequest:
    """Normalize a free-form chat request into a structured PPTX request.

    Main path uses DSPy planning. If no external LM is configured or the configured LM
    cannot produce the needed schema, a deterministic planner is used through the same
    DSPy interface. Final safety net: direct heuristic parsing.
    """

    configured_lm = dspy.settings.lm
    if configured_lm is not None:
        try:
            return _parse_with_predictor(chat_text, configured_lm, parser_mode="dspy-configured")
        except Exception:
            pass

    try:
        return _parse_with_predictor(chat_text, RuleBasedPPTXChatLM(), parser_mode="dspy-rulebased")
    except Exception:
        fallback = _build_rulebased_plan(chat_text)
        return PPTXChatRequest(
            operation=fallback["operation"],
            template_path=fallback["template_path"] or None,
            output_path=fallback["output_path"] or None,
            output_dir=fallback["output_dir"],
            user_input=fallback["content"],
            fields=fallback["fields"],
            raw_chat=chat_text,
            parser_mode="regex-fallback",
            planner_reasoning=fallback["reasoning"],
            planner_confidence=fallback["confidence"],
        )


def execute_chat_request(chat_text: str) -> dict[str, Any]:
    """Execute a free-form chat request using the existing PPTX logic."""

    request = parse_chat_request(chat_text)
    result: dict[str, Any] = {"request": asdict(request)}

    if request.operation == "analyze":
        if not request.template_path:
            raise ValueError("Chat request did not include a template .pptx path to analyze.")
        result.update(analyze_template(request.template_path))
        return result

    if request.operation == "create":
        if not request.output_path:
            raise ValueError("Chat request did not include an output .pptx path for template creation.")
        if not request.fields:
            raise ValueError("Chat request did not include template fields. Use 'fields: company, date'.")
        created_path = create_template_from_spec(request.output_path, request.fields)
        result.update({"success": True, "output_path": created_path, "fields": request.fields})
        return result

    if not request.template_path:
        raise ValueError("Chat request did not include a template .pptx path to fill.")

    output_dir = Path(request.output_dir)
    run_result = run_pptx_agent(
        template_path=request.template_path,
        user_input=request.user_input,
        output_dir=output_dir,
        output_path=request.output_path,
        interactive=False,
    )
    result.update(run_result)
    return result


def run_chat_cli(argv: list[str] | None = None) -> int:
    """CLI entry for free-form chat requests."""

    parser = argparse.ArgumentParser(
        description="Model-driven natural-language chat entry for PPTX workflows"
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Free-form request. If omitted, stdin is read.",
    )
    args = parser.parse_args(argv)

    chat_text = args.message.strip() if args.message else input("PPTX chat request> ").strip()
    result = execute_chat_request(chat_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "PPTXChatRequest",
    "PlanPPTXChatRequest",
    "RuleBasedPPTXChatLM",
    "execute_chat_request",
    "parse_chat_request",
    "run_chat_cli",
]
