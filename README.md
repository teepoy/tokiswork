# tokiswork

一个最小可运行的 DSPy CSV 处理流程示例：

1. 读取 CSV 表头与 prompt。
2. 通过 DSPy `Predict` 生成一段 `polars` 数据处理函数代码。
3. 在受限执行环境里加载并运行这段代码。
4. 输出结果、代码片段与元信息；结果较大时自动写入 `result.csv`。

## 安装

```bash
uv sync
```

## 运行示例

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

## 输出产物

每次运行会在 `runs/<timestamp>/` 下生成：

- `prompt.txt`：本次 prompt
- `*.py`：DSPy 生成的数据处理函数
- `result_preview.json`：结果预览
- `result.csv`：结果较大时生成的完整结果
- `metadata.json`：源文件、代码路径、执行器信息、结果位置等元信息

## 默认模式

仓库默认使用一个本地 `RuleBasedCodegenLM` 来模拟 DSPy 的代码生成流程，方便在没有外部模型密钥时本地验证。

若你已经配置了真实模型，也可以使用：

```bash
DSPY_MODEL=openai/gpt-4o-mini uv run tokiswork-dspy \
  --csv examples/input.csv \
  --prompt-file examples/prompt.txt \
  --real-lm
```
