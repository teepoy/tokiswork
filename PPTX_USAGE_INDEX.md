# PPTX Usage Index

## 入口总览

### 结构化 CLI

```bash
uv run tokiswork-pptx --help
```

子命令：
- `analyze`
- `create`
- `fill`
- `chat`

### 纯 chat 入口

```bash
uv run tokiswork-pptx-chat "请分析 template.pptx 里有哪些字段"
```

---

## 关键文件

- `src/tokiswork_dspy/pptx_core.py` — core logic
- `src/tokiswork_dspy/pptx_chat.py` — chat parsing / request normalization
- `src/tokiswork_dspy/pptx_cli.py` — CLI entry
- `src/tokiswork_dspy/pptx_agent.py` — backward-compatible wrapper
- `examples/pptx_examples.py` — examples
- `test_pptx_agent.py` — smoke test

---

## 文档顺序

1. `README.md`
2. `PPTX_QUICKSTART.md`
3. `PPTX_AGENT.md`

---

## 常用命令

```bash
uv run python examples/pptx_examples.py
uv run python test_pptx_agent.py
uv run tokiswork-pptx analyze demo_template.pptx
uv run tokiswork-pptx-chat "用 demo_template.pptx 生成一份报告，保存到 output/result.pptx，内容是 Acme Corp Q1 2026 总结"
```
