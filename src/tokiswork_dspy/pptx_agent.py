"""Backward-compatible exports for PPTX agent core logic.

Prefer importing from :mod:`tokiswork_dspy.pptx_core` for new code.
"""

from .pptx_core import (
    AnalyzeTemplate,
    ExtractInformation,
    GenerateUserPrompt,
    PPTXAgentResult,
    PPTXReActAgent,
    PPTXTemplateParser,
    ProcessUserResponse,
    TemplateField,
    analyze_template,
    create_simple_template,
    create_template_from_spec,
    run_pptx_agent,
)

__all__ = [
    "AnalyzeTemplate",
    "ExtractInformation",
    "GenerateUserPrompt",
    "PPTXAgentResult",
    "PPTXReActAgent",
    "PPTXTemplateParser",
    "ProcessUserResponse",
    "TemplateField",
    "analyze_template",
    "create_simple_template",
    "create_template_from_spec",
    "run_pptx_agent",
]
