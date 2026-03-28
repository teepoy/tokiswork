from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .pipeline import build_pipeline


def _load_gradio():
    try:
        import gradio as gr  # type: ignore

        return gr
    except ValueError as exc:
        if "Unknown scheme for proxy URL" not in str(exc):
            raise
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            value = os.environ.get(key, "")
            if value.startswith("socks://"):
                os.environ.pop(key, None)
        import gradio as gr  # type: ignore

        return gr


DEFAULT_PROMPT = "请描述你希望对这个 CSV 做什么处理，例如：按 city 汇总 sales。"

gr = _load_gradio()


def run_gradio_pipeline(
    csv_path: str,
    prompt: str,
    output_dir: str = "runs",
    use_real_lm: bool = False,
    request: gr.Request | None = None,
) -> tuple[str, str, str, str]:
    csv_path = (csv_path or "").strip()
    prompt = (prompt or "").strip()
    output_dir = (output_dir or "runs").strip()

    # Extract username from request if available (for logging/tracking)
    username = request.username if request else "anonymous"

    if not csv_path:
        raise gr.Error("请输入 share disk 上的 CSV 路径。")
    if not prompt:
        raise gr.Error("请输入处理 prompt。")

    pipeline = build_pipeline(use_real_lm=use_real_lm)
    result = pipeline(csv_path=csv_path, prompt=prompt, output_dir=output_dir)

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    preview = json.loads(result.preview_path.read_text(encoding="utf-8"))
    code = result.code_path.read_text(encoding="utf-8")

    lines = [
        "运行完成。",
        f"- 输入 CSV：`{result.source_csv}`",
        f"- 输出目录：`{result.run_dir}`",
        f"- Prompt 记录：`{result.prompt_path}`",
        f"- 生成代码：`{result.code_path}`",
        f"- 结果预览：`{result.preview_path}`",
    ]
    if result.result_path:
        lines.append(f"- 完整结果 CSV：`{result.result_path}`")
    else:
        lines.append("- 完整结果 CSV：本次未生成，直接看结果预览即可")

    return (
        "\n".join(lines),
        json.dumps(metadata, ensure_ascii=False, indent=2),
        code,
        json.dumps(preview, ensure_ascii=False, indent=2),
    )


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="tokiswork Gradio Demo") as demo:
        gr.Markdown(
            """
# tokiswork Gradio Demo

直接输入 **share disk 上的 CSV 路径** 与处理 prompt，内部会复用现有 DSPy CSV pipeline，
并把输出写到 `runs/<timestamp>/`（或你指定的目录）下。
""".strip()
        )

        with gr.Row():
            csv_path = gr.Textbox(
                label="CSV 路径（share disk）",
                placeholder="例如：/share/disk/project/input.csv",
            )
            output_dir = gr.Textbox(
                label="输出目录",
                value="runs",
                placeholder="例如：runs 或 /share/disk/project/runs",
            )

        prompt = gr.Textbox(
            label="处理 prompt",
            lines=8,
            value=DEFAULT_PROMPT,
            placeholder="例如：按 city 汇总 sales，并按总销售额降序排序。",
        )
        use_real_lm = gr.Checkbox(
            label="使用真实 DSPy 模型（需要预先设置 DSPY_MODEL）",
            value=False,
        )
        run_button = gr.Button("运行 pipeline", variant="primary")

        status = gr.Markdown(label="运行结果")
        with gr.Row():
            metadata = gr.Code(label="metadata.json", language="json")
            preview = gr.Code(label="result_preview.json", language="json")
        code = gr.Code(label="生成的 transform 代码", language="python")

        run_button.click(
            fn=run_gradio_pipeline,
            inputs=[csv_path, prompt, output_dir, use_real_lm],
            outputs=[status, metadata, code, preview],
        )

    return demo


def launch_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch tokiswork Gradio demo")
    parser.add_argument("--host", default="127.0.0.1", help="Host for Gradio server")
    parser.add_argument("--port", type=int, default=7860, help="Port for Gradio server")
    parser.add_argument("--share", action="store_true", help="Enable Gradio share link")
    args = parser.parse_args(argv)

    demo = build_demo()
    demo.launch(server_name=args.host, server_port=args.port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch_cli())
