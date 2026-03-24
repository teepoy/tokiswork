"""CLI entrypoints for PPTX workflows."""

from __future__ import annotations

import argparse
import json

from .pptx_chat import execute_chat_request
from .pptx_core import analyze_template, create_template_from_spec, run_pptx_agent


def run_cli(argv: list[str] | None = None) -> int:
    """Command-line interface for PPTX workflows."""

    parser = argparse.ArgumentParser(
        description="DSPy PPTX agent with both structured CLI and chat-style entrypoints"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a PPTX template")
    analyze_parser.add_argument("template", help="Path to PPTX template")

    create_parser = subparsers.add_parser("create", help="Create a template from spec")
    create_parser.add_argument("output", help="Output path for template")
    create_parser.add_argument("--fields", required=True, help="JSON spec of fields")

    fill_parser = subparsers.add_parser("fill", help="Fill a template")
    fill_parser.add_argument("template", help="Path to PPTX template")
    fill_parser.add_argument("--input", required=True, help="User input/description")
    fill_parser.add_argument("--output-dir", default="pptx_runs", help="Output directory")
    fill_parser.add_argument("--output-path", help="Optional explicit output PPTX path")
    fill_parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    fill_parser.add_argument("--use-real-lm", action="store_true", help="Use real LM")

    chat_parser = subparsers.add_parser(
        "chat",
        help="Run the PPTX workflow from a single natural-language request",
    )
    chat_parser.add_argument("message", help="Free-form chat request")

    args = parser.parse_args(argv)

    if args.command == "analyze":
        print(json.dumps(analyze_template(args.template), ensure_ascii=False, indent=2))
        return 0

    if args.command == "create":
        spec = json.loads(args.fields)
        print(f"Template created at: {create_template_from_spec(args.output, spec)}")
        return 0

    if args.command == "fill":
        print(
            json.dumps(
                run_pptx_agent(
                    template_path=args.template,
                    user_input=args.input,
                    output_dir=args.output_dir,
                    output_path=args.output_path,
                    use_real_lm=args.use_real_lm,
                    interactive=args.interactive,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "chat":
        print(json.dumps(execute_chat_request(args.message), ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


__all__ = ["run_cli"]
