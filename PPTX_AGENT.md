# PPTX Agent

## 现在的结构

PPTX 相关实现已整理为 4 层：

1. **Core logic** — `src/tokiswork_dspy/pptx_core.py`
   - `PPTXTemplateParser`
   - `PPTXReActAgent`
   - `run_pptx_agent()`
   - `analyze_template()`
   - `create_template_from_spec()`
2. **Chat parsing / request normalization** — `src/tokiswork_dspy/pptx_chat.py`
   - `parse_chat_request()`
   - `execute_chat_request()`
   - `PPTXChatRequest`
3. **CLI entry** — `src/tokiswork_dspy/pptx_cli.py`
   - `analyze`
   - `create`
   - `fill`
   - `chat`
4. **Compatibility layer** — `src/tokiswork_dspy/pptx_agent.py`
   - 保留原始导入路径，内部转发到 `pptx_core`

---

## 支持的两种入口

### 1. Structured CLI

适合脚本、自动化、明确参数调用。

```bash
uv run tokiswork-pptx analyze template.pptx
uv run tokiswork-pptx create output.pptx --fields '{"company":"Company","date":"Date"}'
uv run tokiswork-pptx fill template.pptx --input "为 Acme Corp 生成季度汇报" --output-dir pptx_runs
```

### 2. Pure Chat Entry

适合直接给一句自然语言，让系统自行抽取：
- 模板路径
- 输出路径
- 目标操作（analyze / create / fill）
- 模板字段或业务描述

运行方式：

```bash
uv run tokiswork-pptx-chat "请分析 ./demo/template.pptx 里有哪些字段"
```

或者：

```bash
uv run tokiswork-pptx chat "用 ./demo/template.pptx 生成一份报告，保存到 ./out/result.pptx，内容是 Acme Corp Q1 2026 总结"
```

---

## Chat 入口目前支持的操作

### Analyze

示例：

```text
请分析 ./examples/pptx_templates/basic_report.pptx 里有哪些可填字段
```

### Fill

示例：

```text
用 ./examples/pptx_templates/basic_report.pptx 生成一份 PPT，保存到 ./examples/pptx_output/acme_q1.pptx。
内容是：Acme Corporation 的 Q1 2026 经营分析，作者 Jane Smith，日期 2026-03-24，摘要写 Sales increased 15% YoY。
```

### Create

示例：

```text
创建模板到 ./examples/pptx_templates/new_template.pptx，fields: company_name, report_title, date, executive_summary
```

> 说明：create 模式当前更适合“简单字段模板”；复杂版式模板仍建议先人工做好 PPTX，再用 `fill` 或 `analyze`。

---

## Python API

### Core API

```python
from tokiswork_dspy.pptx_core import analyze_template, run_pptx_agent

analysis = analyze_template("template.pptx")
result = run_pptx_agent(
    template_path="template.pptx",
    user_input="为 Acme Corp 生成季度汇报",
    output_dir="pptx_runs",
)
```

### Chat API

```python
from tokiswork_dspy.pptx_chat import execute_chat_request

result = execute_chat_request(
    "用 template.pptx 生成一份报告，保存到 outputs/final.pptx，内容是 Acme Corp Q1 2026 总结"
)
```

---

## 兼容性

如果旧代码仍在 import：

```python
from tokiswork_dspy.pptx_agent import PPTXReActAgent, PPTXTemplateParser
```

依然可用；只是新代码推荐改用：

```python
from tokiswork_dspy.pptx_core import PPTXReActAgent, PPTXTemplateParser
```

---

## 本地验证建议

```bash
uv run python examples/pptx_examples.py
uv run python test_pptx_agent.py
uv run tokiswork-pptx --help
uv run tokiswork-pptx-chat "请分析 examples/pptx_templates/basic_report.pptx"
```
