#!/usr/bin/env python
"""Minimal smoke test for PPTX structured + chat entry."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import dspy

from tokiswork_dspy.pptx_chat import execute_chat_request, parse_chat_request
from tokiswork_dspy.pptx_core import (
    PPTXTemplateParser,
    create_simple_template,
    run_pptx_agent,
)


class SimplePPTXLM(dspy.BaseLM):
    """Tiny deterministic LM for smoke testing."""

    def __init__(self):
        super().__init__(model="simple-pptx", model_type="chat")

    def forward(self, prompt=None, messages=None, **kwargs):
        user_text = ""
        for msg in messages or []:
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
        user_text = user_text or prompt or ""
        lower_text = user_text.lower()
        extracted = {}

        if "acme" in lower_text:
            extracted["company"] = "Acme Corporation"
        if "q1" in lower_text:
            extracted["quarter"] = "Q1 2026"
        if "2026-03-24" in lower_text:
            extracted["date"] = "2026-03-24"

        expected_fields = ["company", "quarter", "date"]
        missing = [f for f in expected_fields if f not in extracted]
        operation = "analyze" if ("analyze" in lower_text or "分析" in lower_text) else "fill"
        template_match = next((token for token in user_text.replace('。', ' ').split() if token.endswith('.pptx')), "")
        output_match = ""
        if "保存到" in user_text:
            output_match = user_text.split("保存到", 1)[1].strip().split()[0].rstrip("。.,，")
        content = f"""[[ ## extracted_data ## ]]
{json.dumps(extracted)}

[[ ## missing_fields ## ]]
{', '.join(missing)}

[[ ## reasoning ## ]]
Deterministic smoke-test extraction.

[[ ## analysis ## ]]
Template analyzed.

[[ ## field_names ## ]]
{', '.join(expected_fields)}

[[ ## user_prompt ## ]]
Please provide: {', '.join(missing)}

[[ ## extracted_values ## ]]
{json.dumps(extracted)}

[[ ## completeness ## ]]
{'Complete' if not missing else 'Partial'}

[[ ## operation ## ]]
{operation}

[[ ## template_path ## ]]
{template_match}

[[ ## output_path ## ]]
{output_match}

[[ ## output_dir ## ]]
pptx_runs

[[ ## fields_json ## ]]
{{}}

[[ ## content ## ]]
{user_text}

[[ ## confidence ## ]]
medium

[[ ## completed ## ]]
"""
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(
            choices=[choice],
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.model,
        )


def main() -> int:
    dspy.configure(lm=SimplePPTXLM())

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        template_path = root / "demo_template.pptx"
        output_path = root / "outputs" / "demo_result.pptx"
        create_simple_template(
            template_path,
            {
                "company": "{{company}}",
                "quarter": "{{quarter}}",
                "date": "{{date}}",
            },
        )

        parser = PPTXTemplateParser(template_path)
        assert parser.get_field_info()["total_fields"] == 3

        structured = run_pptx_agent(
            template_path=template_path,
            user_input="Acme Q1 2026 summary. Date 2026-03-24.",
            output_dir=root / "outputs",
            output_path=output_path,
        )
        assert structured["success"] is True
        assert Path(structured["output_path"]).exists()

        chat_text = (
            f"用 {template_path} 生成一份 PPT，保存到 {root / 'outputs' / 'chat_result.pptx'}。"
            "内容是：Acme 的 Q1 2026 总结，日期 2026-03-24。"
        )
        parsed = parse_chat_request(chat_text)
        assert parsed.operation == "fill"
        assert parsed.template_path and parsed.template_path.endswith("demo_template.pptx")
        assert parsed.parser_mode in {"dspy-configured", "dspy-rulebased", "regex-fallback"}

        chat_result = execute_chat_request(chat_text)
        assert chat_result["success"] is True
        assert Path(chat_result["output_path"]).exists()

        print("PPTX smoke test passed.")
        print(json.dumps({
            "structured_output": structured["output_path"],
            "chat_output": chat_result["output_path"],
        }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
