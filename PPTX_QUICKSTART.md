# PPTX Quick Start

## 安装

```bash
cd /home/jin/.openclaw/workspace/tokiswork
uv sync
```

## 先跑一个最小示例

```bash
uv run python examples/pptx_examples.py
```

---

## 方式一：CLI

### 创建模板

```bash
uv run tokiswork-pptx create demo_template.pptx \
  --fields '{"company":"Company","date":"Date","summary":"Summary"}'
```

### 分析模板

```bash
uv run tokiswork-pptx analyze demo_template.pptx
```

### 填充模板

```bash
uv run tokiswork-pptx fill demo_template.pptx \
  --input "为 Acme Corp 生成 Q1 2026 汇报，日期 2026-03-24，摘要写销售增长 15%" \
  --output-dir pptx_runs
```

---

## 方式二：纯 chat 入口

### 独立 chat 命令

```bash
uv run tokiswork-pptx-chat "请分析 demo_template.pptx 里有哪些字段"
```

### 统一 CLI 下的 chat 子命令

```bash
uv run tokiswork-pptx chat "用 demo_template.pptx 生成一份报告，保存到 output/demo_result.pptx，内容是 Acme Corp 的季度回顾，摘要写销售增长 15%"
```

---

## Chat 输入示例

### 分析模板

```text
请分析 ./demo/template.pptx 这个模板里有哪些可填字段
```

### 填充模板

```text
用 ./demo/template.pptx 生成一份 PPT，输出到 ./output/final.pptx。
内容是：Acme Corporation 的 Q1 2026 经营分析，作者 Jane Smith，日期 2026-03-24，摘要写 Sales increased 15% YoY。
```

### 创建模板

```text
创建模板到 ./demo/new_template.pptx，fields: company_name, report_title, date, executive_summary
```

---

## Python 用法

```python
from tokiswork_dspy.pptx_chat import execute_chat_request

result = execute_chat_request(
    "用 ./demo/template.pptx 生成一份报告，保存到 ./output/final.pptx，内容是 Acme Corp Q1 2026 总结"
)
print(result)
```

---

## 验证

```bash
uv run python test_pptx_agent.py
uv run tokiswork-pptx --help
uv run tokiswork-pptx-chat "请分析 demo_template.pptx"
```
