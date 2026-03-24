# AGENT.md

## Project Notes

- This is a Python project.
- Use `uv` to manage dependencies, virtual environments, and lockfiles.
- Prefer `uv run ...` for running commands and scripts.
- Prefer `uv add ...` / `uv remove ...` for dependency changes.
- Keep `pyproject.toml` and `uv.lock` in sync when updating dependencies.
- When adding runnable entry points, register them in `pyproject.toml` if appropriate.
- Prefer small, practical changes that preserve the existing project structure.
- Reuse the existing DSPy pipeline and related modules instead of creating duplicate implementations.
- If you add docs or examples, keep them aligned with the actual CLI and project behavior.

## PPTX ReAct Agent

A comprehensive DSPy-based system for intelligent PPTX template processing has been added to the project.

### What It Does

The PPTX ReAct Agent automates the workflow of:
1. **Parsing** PPTX template files to detect fillable placeholder regions
2. **Extracting** relevant information from user descriptions
3. **Reasoning** about missing fields and using defaults
4. **Interacting** with users when additional information is needed
5. **Generating** new PPTX files with all content filled in

### Key Features

- **Flexible placeholder detection**: Supports `{{field}}`, `[FIELD]`, and `<<field>>` formats
- **Smart field classification**: Distinguishes required vs optional fields, with default values
- **Multi-step reasoning**: Full traceability of agent decision-making process
- **Format preservation**: Maintains original PPTX formatting (fonts, colors, sizes)
- **Partial information handling**: Works with incomplete user input, asks for missing data when needed
- **DSPy integration**: Full compatibility with DSPy signatures and language models

### Quick Start

```bash
# Create a test template
uv run python -c "
from tokiswork_dspy.pptx_core import create_simple_template
create_simple_template('template.pptx', {
    'company': '{{company}}',
    'date': '{{date}}',
    'summary': '{{summary}}'
})
"

# Analyze template structure
uv run tokiswork-pptx analyze template.pptx

# Fill template from user input
uv run tokiswork-pptx fill template.pptx \
  --input "Create Q1 report for Acme Corp" \
  --output-dir output

# Or use the pure chat entry
uv run tokiswork-pptx-chat "用 template.pptx 生成一份 PPT，保存到 output/result.pptx，内容是 Acme Corp Q1 report"
```

### Module Structure

**Core modules:**
- `src/tokiswork_dspy/pptx_core.py` - core logic
- `src/tokiswork_dspy/pptx_chat.py` - chat parsing / request normalization
- `src/tokiswork_dspy/pptx_cli.py` - command-line interface
- `src/tokiswork_dspy/pptx_agent.py` - backward-compatible wrapper
- `examples/pptx_examples.py` - usage examples

**Key classes:**
- `PPTXTemplateParser` - Parses PPTX files and extracts field information
- `PPTXReActAgent` - Orchestrates the reasoning loop
- `PPTXAgentResult` - Structured result with filled fields and metadata

**DSPy Signatures:**
- `AnalyzeTemplate` - Template structure analysis
- `ExtractInformation` - Field value extraction from user input
- `GenerateUserPrompt` - User-friendly prompts for missing data
- `ProcessUserResponse` - Parsing user responses

### Python API Example

```python
from tokiswork_dspy.pptx_agent import PPTXReActAgent

# Create agent
agent = PPTXReActAgent()

# Run processing
result = agent.forward(
    template_path="template.pptx",
    user_input="Create Q1 2026 report for TechCorp. Revenue $15M.",
    output_path="output.pptx",
    user_interaction_callback=None
)

# Access results
print(f"Generated: {result.output_path}")
print(f"Filled: {result.filled_fields}")
print(f"Reasoning trace: {result.metadata['thought_log']}")
```

### Advanced Usage

Configure custom DSPy language models:
```python
import dspy
from tokiswork_dspy.pptx_agent import PPTXReActAgent

# Use real LM (requires API keys)
dspy.configure(lm=dspy.LM('openai/gpt-4'))

# Create agent with custom modules
agent = PPTXReActAgent(
    analyze_module=dspy.Predict(AnalyzeTemplate),
    extract_module=dspy.Predict(ExtractInformation),
)

# Run with interactive user prompts
def ask_user(prompt):
    print(prompt)
    return input("> ")

result = agent.forward(
    template_path="template.pptx",
    user_input="initial description",
    output_path="output.pptx",
    user_interaction_callback=ask_user,
)
```

### Testing

Run the comprehensive test suite:
```bash
uv run python test_pptx_agent.py
uv run python examples/pptx_examples.py
```

**Test coverage:**
- Template creation and parsing
- Field extraction from user input
- Handling of missing required fields
- Output PPTX generation
- Agent reasoning trace
- Custom workflow execution

### Documentation

See [PPTX_AGENT.md](./PPTX_AGENT.md) for comprehensive documentation including:
- Architecture and design
- Component descriptions
- Usage patterns and examples
- Troubleshooting guide
- API reference

### Dependencies Added

- `python-pptx>=0.6.23` - PPTX file parsing and generation
- `lxml>=6.0.2` - XML processing (required by python-pptx)
- `xlsxwriter>=3.2.9` - Spreadsheet support (optional enhancement)

### Example Workflows

1. **Simple template filling** - User provides complete information, agent fills all fields
2. **Interactive mode** - Agent asks user for missing required fields
3. **Partial information** - Agent uses defaults for optional fields
4. **Batch processing** - Fill multiple templates with structured data
5. **Custom extraction** - Implement specialized information extraction logic

### Performance

- Template analysis: O(slides × shapes)
- Information extraction: Depends on LM used
- PPTX generation: < 1s typically
- Memory usage: Minimal (presentations loaded in memory only)

### Future Enhancements

Potential improvements:
- [ ] Table and complex shape content generation
- [ ] Image insertion from descriptions  
- [ ] Advanced layout and styling options
- [ ] Multi-slide template libraries
- [ ] Batch processing with progress tracking
- [ ] Custom field validators
- [ ] Template version management
- [ ] Export to other formats
- [ ] Web interface (Gradio integration)
