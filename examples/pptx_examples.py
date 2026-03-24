"""Examples for PPTX core + chat entry."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import dspy

from tokiswork_dspy.pptx_chat import execute_chat_request, parse_chat_request
from tokiswork_dspy.pptx_core import (
    PPTXTemplateParser,
    create_simple_template,
    run_pptx_agent,
)


class ExamplePPTXLM(dspy.BaseLM):
    """Deterministic LM so examples can run locally without external config."""

    def __init__(self):
        super().__init__(model="example-pptx", model_type="chat")

    def forward(self, prompt=None, messages=None, **kwargs):
        user_text = ""
        for msg in messages or []:
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
        user_text = user_text or prompt or ""
        lower = user_text.lower()
        extracted = {}

        if "acme" in lower:
            extracted["company_name"] = "Acme Corporation"
        if "q1 2026" in lower:
            extracted["report_title"] = "Q1 2026 Business Review"
        if "jane smith" in lower:
            extracted["author"] = "Jane Smith"
        if "2026-03-24" in lower:
            extracted["date"] = "2026-03-24"
        if "sales increased 15% yoy" in lower:
            extracted["executive_summary"] = "Sales increased 15% YoY."

        expected = [
            "company_name",
            "report_title",
            "date",
            "author",
            "executive_summary",
        ]
        missing = [f for f in expected if f not in extracted]
        content = f"""[[ ## extracted_data ## ]]
{json.dumps(extracted)}

[[ ## missing_fields ## ]]
{', '.join(missing)}

[[ ## reasoning ## ]]
Deterministic example extraction.

[[ ## analysis ## ]]
Template analyzed.

[[ ## field_names ## ]]
{', '.join(expected)}

[[ ## user_prompt ## ]]
Please provide: {', '.join(missing)}

[[ ## extracted_values ## ]]
{json.dumps(extracted)}

[[ ## completeness ## ]]
{'Complete' if not missing else 'Partial'}

[[ ## completed ## ]]
"""
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(
            choices=[choice],
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            model=self.model,
        )


def prepare_template() -> Path:
    template_dir = Path("examples/pptx_templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "basic_report.pptx"
    create_simple_template(
        template_path,
        {
            "company_name": "{{company_name}}",
            "report_title": "{{report_title}}",
            "date": "{{date}}",
            "author": "{{author}}",
            "executive_summary": "{{executive_summary}}",
        },
    )
    return template_path


def example_analyze(template_path: Path) -> None:
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Analyze template structure")
    print("=" * 70)
    parser = PPTXTemplateParser(template_path)
    print(json.dumps(parser.get_field_info(), ensure_ascii=False, indent=2))


def example_fill_cli_style(template_path: Path) -> None:
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Fill template via structured API")
    print("=" * 70)
    result = run_pptx_agent(
        template_path=template_path,
        user_input=(
            "Acme Corporation Q1 2026 business review. "
            "Author Jane Smith. Date 2026-03-24. "
            "Executive summary: Sales increased 15% YoY."
        ),
        output_dir="examples/pptx_output",
        output_path="examples/pptx_output/acme_q1_structured.pptx",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def example_chat_parse(template_path: Path) -> None:
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Parse free-form chat request")
    print("=" * 70)
    chat = (
        f"用 {template_path} 生成一份 PPT，保存到 examples/pptx_output/acme_q1_chat.pptx。"
        "内容是：Acme Corporation 的 Q1 2026 经营分析，作者 Jane Smith，日期 2026-03-24，"
        "摘要写 Sales increased 15% YoY。"
    )
    print(json.dumps(parse_chat_request(chat).__dict__, ensure_ascii=False, indent=2))


def example_chat_execute(template_path: Path) -> None:
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Execute free-form chat request")
    print("=" * 70)
    chat = (
        f"用 {template_path} 生成一份 PPT，保存到 examples/pptx_output/acme_q1_chat.pptx。"
        "内容是：Acme Corporation 的 Q1 2026 经营分析，作者 Jane Smith，日期 2026-03-24，"
        "摘要写 Sales increased 15% YoY。"
    )
    print(json.dumps(execute_chat_request(chat), ensure_ascii=False, indent=2))


def example_chat_create() -> None:
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Create template via chat request")
    print("=" * 70)
    chat = (
        "创建模板到 examples/pptx_templates/chat_created_template.pptx，"
        "fields: company_name, report_title, date, executive_summary"
    )
    print(json.dumps(execute_chat_request(chat), ensure_ascii=False, indent=2))


def main() -> int:
    dspy.configure(lm=ExamplePPTXLM())
    template_path = prepare_template()
    example_analyze(template_path)
    example_fill_cli_style(template_path)
    example_chat_parse(template_path)
    example_chat_execute(template_path)
    example_chat_create()
    print("\nAll PPTX examples completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
