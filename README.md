# tokiswork

一个最小可运行的 DSPy CSV 处理流程示例：

1. 读取 CSV 表头与 prompt。
2. 通过 DSPy `Predict` 生成一段 `polars` 数据处理函数代码。
3. 在受限执行环境里加载并运行这段代码。
4. 输出结果、代码片段与元信息；结果较大时自动写入 `result.csv`。

现在仓库同时提供：

- CLI 入口：适合脚本/终端使用
- Gradio Demo：适合手动输入 **share disk 路径** 做交互式验证

## 安装

```bash
uv sync
```

## CLI 运行示例

```bash
uv run tokiswork-dspy \
  --csv examples/input.csv \
  --prompt-file examples/prompt.txt
```

或：

```bash
uv run python main.py \
  --csv examples/input.csv \
  --prompt-file examples/prompt.txt
```

## 启动 Gradio Demo

推荐：

```bash
uv run tokiswork-gradio --host 0.0.0.0 --port 7860
```

或直接运行模块：

```bash
uv run python -m tokiswork_dspy.gradio_app --host 0.0.0.0 --port 7860
```

启动后，在界面中：

1. 在 **CSV 路径（share disk）** 输入框填写 CSV 文件路径，例如 `/share/disk/project/input.csv`
2. 在 **处理 prompt** 输入框填写你的需求，例如“按 city 汇总 sales，并按总销售额降序排序”
3. 如需自定义产物位置，可修改 **输出目录**（默认是 `runs`）
4. 点击 **运行 pipeline**

> 注意：这里不提供单独的文件上传控件，默认工作流就是直接输入 share disk 上的 CSV 路径。

## Gradio 输出内容

每次运行会复用现有 pipeline，并在 `runs/<timestamp>/`（或你指定的输出目录）下生成：

- `prompt.txt`：本次 prompt
- `*.py`：DSPy 生成的数据处理函数
- `result_preview.json`：结果预览
- `result.csv`：结果较大时生成的完整结果
- `metadata.json`：源文件、代码路径、执行器信息、结果位置等元信息

在 Gradio 页面中还能直接看到：

- 本次运行的输出目录
- `metadata.json` 内容
- 生成的 transform 代码
- `result_preview.json` 内容

如果本次结果较小，可能不会生成 `result.csv`，这时直接查看 `result_preview.json` 即可。

## 默认模式

仓库默认使用一个本地 `RuleBasedCodegenLM` 来模拟 DSPy 的代码生成流程，方便在没有外部模型密钥时本地验证。

若你已经配置了真实模型，也可以使用 CLI：

```bash
DSPY_MODEL=openai/gpt-4o-mini uv run tokiswork-dspy \
  --csv examples/input.csv \
  --prompt-file examples/prompt.txt \
  --real-lm
```

或在 Gradio 页面勾选“使用真实 DSPy 模型（需要预先设置 DSPY_MODEL）”。
