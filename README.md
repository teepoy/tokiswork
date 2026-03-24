# tokiswork

一个最小可运行的 DSPy 工作台，目前包含两条能力线：

1. **CSV prompt pipeline**：读取 CSV 和 prompt，生成并执行 `polars` 数据处理代码。
2. **PPTX agent**：分析 / 创建 / 填充 PPTX 模板，支持传统 CLI 和新的纯 chat 入口。

## 安装

```bash
uv sync
```

---

## CSV Pipeline

### CLI 运行示例

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

### 启动 Gradio Demo

```bash
uv run tokiswork-gradio --host 0.0.0.0 --port 7860
```

或：

```bash
uv run python -m tokiswork_dspy.gradio_app --host 0.0.0.0 --port 7860
```

---

## PPTX Agent

PPTX 相关实现现在分为 4 层：

- `src/tokiswork_dspy/pptx_core.py`：core logic
- `src/tokiswork_dspy/pptx_chat.py`：DSPy-driven chat planning / request normalization（失败时退回确定性 fallback）
- `src/tokiswork_dspy/pptx_cli.py`：CLI entry
- `examples/pptx_examples.py` + `PPTX_*.md`：docs/examples

兼容层保留在：

- `src/tokiswork_dspy/pptx_agent.py`

### 1) 传统 CLI 用法

#### 分析模板

```bash
uv run tokiswork-pptx analyze template.pptx
```

#### 创建模板

```bash
uv run tokiswork-pptx create demo_template.pptx \
  --fields '{"company":"Company","date":"Date","summary":"Summary"}'
```

#### 填充模板

```bash
uv run tokiswork-pptx fill demo_template.pptx \
  --input "为 Acme Corp 生成 Q1 2026 汇报，日期 2026-03-24，摘要是销售增长 15%" \
  --output-dir pptx_runs
```

如需显式输出文件名：

```bash
uv run tokiswork-pptx fill demo_template.pptx \
  --input "为 Acme Corp 生成季度汇报" \
  --output-path outputs/acme_q1_report.pptx
```

### 2) 纯 chat 入口

chat 入口现在默认走 **DSPy + model-driven planning**：先让 `pptx_chat.py` 做意图识别（`analyze/create/fill`）、路径/字段/内容抽取，再复用现有 `pptx_core.py` 的能力执行。若当前没有可用模型，或模型输出不完整，则自动回退到仓库内置的 deterministic planner。

新增运行方式：

```bash
uv run tokiswork-pptx-chat "请分析 template.pptx 这个模板里有哪些字段"
```

或通过统一 CLI 的 `chat` 子命令：

```bash
uv run tokiswork-pptx chat "用 template.pptx 生成一份报告，保存到 outputs/final.pptx，内容是：Acme Corp 的 Q1 2026 经营回顾，摘要写销售增长 15%"
```

### chat 输入示例

#### 示例 1：分析模板

```text
请分析 ./examples/pptx_templates/basic_report.pptx 里有哪些可填字段
```

#### 示例 2：自然语言填充模板

```text
用 ./examples/pptx_templates/basic_report.pptx 生成一份 PPT，输出到 ./examples/pptx_output/acme_q1.pptx。
内容是：Acme Corporation 的 Q1 2026 经营分析，作者 Jane Smith，日期 2026-03-24，摘要写 Sales increased 15% YoY。
```

#### 示例 3：自然语言创建模板

```text
创建模板到 ./examples/pptx_templates/new_template.pptx，fields: company_name, report_title, date, executive_summary
```

### Python API

#### 结构化调用

```python
from tokiswork_dspy.pptx_core import run_pptx_agent

result = run_pptx_agent(
    template_path="template.pptx",
    user_input="为 Acme Corp 生成季度报告",
    output_dir="pptx_runs",
)
```

#### chat 调用

```python
from tokiswork_dspy.pptx_chat import execute_chat_request

result = execute_chat_request(
    "用 template.pptx 生成一份报告，保存到 outputs/out.pptx，内容是 Acme Corp Q1 2026 总结"
)
```

更多说明见：

- `PPTX_AGENT.md`
- `PPTX_QUICKSTART.md`
- `PPTX_USAGE_INDEX.md`

---

## 默认模式

CSV pipeline 仍保留本地可验证的规则式 LM；PPTX chat 入口则升级为 **DSPy planner 优先、deterministic fallback 保底**。

- 若已通过 `dspy.configure(lm=...)` 配置真实模型：chat 解析优先使用该模型。
- 若未配置模型，或模型不按预期返回规划字段：自动切回内置 `RuleBasedPPTXChatLM` / heuristic fallback。
- 底层 PPTX 分析、创建、填充逻辑仍复用 `pptx_core.py`，没有重复实现 PPTX 操作。
