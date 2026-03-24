"""Natural-language chat entry for PPTX workflows."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .pptx_core import analyze_template, create_template_from_spec, run_pptx_agent

_PATH_RE = re.compile(r"(?:[\w./~-]+\.pptx)")
_QUOTED_PATH_RE = re.compile(r'(["\'])(.+?\.pptx)\1')


@dataclass
class PPTXChatRequest:
    operation: str = "fill"
    template_path: str | None = None
    output_path: str | None = None
    output_dir: str = "pptx_runs"
    user_input: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    raw_chat: str = ""


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
    if any(k in text for k in ["analyze", "inspect", "查看模板", "分析模板"]):
        return "analyze"
    if any(k in text for k in ["create template", "make template", "新建模板", "创建模板"]):
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
    patterns = [
        r'save (?:it )?(?:as|to)\s*["\']?([^"\'\n]+\.pptx)["\']?',
        r'\boutput(?: path)?\b\s*(?:is|=|to)?\s*["\']?([^"\'\n]+\.pptx)["\']?',
        r'输出(?:路径|文件)?(?:是|为)?\s*["\']?([^"\'\n]+\.pptx)["\']?',
        r'保存到\s*["\']?([^"\'\n]+\.pptx)["\']?',
    ]
    for pattern in patterns:
        match = re.search(pattern, chat_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_fields_spec(chat_text: str) -> dict[str, str]:
    quoted_json = re.search(r"\{.*\}", chat_text, re.DOTALL)
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
        token.strip(" `，,。")
        for token in re.split(r"[,，]\s*", fields_text)
        if token.strip(" `，,。")
    ]
    return {name: name for name in names}


def parse_chat_request(chat_text: str) -> PPTXChatRequest:
    """Normalize a free-form chat request into a structured PPTX request."""

    paths = _extract_paths(chat_text)
    operation = _infer_operation(chat_text)
    template_path = paths[0] if paths else None
    output_path = _extract_output_path(chat_text)

    if operation == "fill" and len(paths) > 1 and not output_path:
        output_path = paths[1]
    if operation == "create" and len(paths) > 0:
        output_path = output_path or paths[0]
        template_path = None

    cleaned_user_input = chat_text.strip()
    if template_path:
        cleaned_user_input = cleaned_user_input.replace(template_path, "[template_path]")
    if output_path:
        cleaned_user_input = cleaned_user_input.replace(output_path, "[output_path]")

    return PPTXChatRequest(
        operation=operation,
        template_path=template_path,
        output_path=output_path,
        output_dir=_extract_output_dir(chat_text),
        user_input=cleaned_user_input,
        fields=_extract_fields_spec(chat_text),
        raw_chat=chat_text,
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
        description="Natural-language chat entry for PPTX workflows"
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
    "execute_chat_request",
    "parse_chat_request",
    "run_chat_cli",
]
