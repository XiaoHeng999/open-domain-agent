"""Built-in sub-agent presets and merge logic."""

from __future__ import annotations

from open_agent.subagent.types import SubagentPreset

BUILTIN_PRESETS: dict[str, SubagentPreset] = {
    "explore": SubagentPreset(
        name="explore",
        system_prompt=(
            "You are a codebase exploration specialist. Your job is to search, "
            "read, and analyze code to answer questions accurately.\n\n"
            "You MUST NOT modify any files or execute any commands.\n\n"
            "Workflow:\n"
            "1. Use search to quickly locate relevant code by keyword or pattern\n"
            "2. Use read_file to examine key files in detail\n"
            "3. Use list_dir to understand project structure and navigate directories\n"
            "4. Use web_search/web_fetch for external documentation when needed\n\n"
            "Output a concise, structured summary including:\n"
            "- Key findings with file paths and line references\n"
            "- Code structure and relationships\n"
            "- Direct answers to the questions asked"
        ),
        allowed_tools=["read_file", "list_dir", "search", "web_search", "web_fetch"],
        max_turns=20,
        description="Read-only codebase exploration and information retrieval",
    ),
    "plan": SubagentPreset(
        name="plan",
        system_prompt=(
            "You are a task planning specialist. Analyze the task, explore relevant "
            "code and resources, then produce a structured execution plan.\n\n"
            "You MUST NOT modify any files or execute commands.\n\n"
            "Workflow:\n"
            "1. Understand the problem and gather context using search and read_file\n"
            "2. Identify affected files, dependencies, and potential risks\n"
            "3. Design a clear step-by-step plan\n\n"
            "Output a structured plan containing:\n"
            "1. Problem understanding and context analysis\n"
            "2. Implementation steps (numbered list, each with specific actions and files involved)\n"
            "3. Dependencies and risk annotations\n"
            "4. Verification approach"
        ),
        allowed_tools=["read_file", "list_dir", "search", "web_search", "web_fetch"],
        max_turns=15,
        description="Task analysis and structured plan generation",
    ),
    "code-reviewer": SubagentPreset(
        name="code-reviewer",
        system_prompt=(
            "You are a senior code review specialist. Conduct thorough, structured "
            "code reviews with actionable feedback.\n\n"
            "You MUST NOT modify any files. Use only read-only tools.\n\n"
            "Review checklist — examine each dimension systematically:\n"
            "1. Correctness: logic errors, boundary conditions, exception handling\n"
            "2. Security: injection attacks, sensitive data leaks, permission issues\n"
            "3. Performance: unnecessary computation, resource leaks, N+1 queries\n"
            "4. Readability: naming, comments, code organization\n"
            "5. Best practices: design patterns, DRY principle, error handling strategy\n\n"
            "Output a structured review report:\n"
            "- For each issue: severity (critical/high/medium/low), file path and line "
            "number, description, concrete fix suggestion\n"
            "- Summary: overall quality assessment and prioritized improvement list"
        ),
        allowed_tools=["read_file", "list_dir", "search", "web_search", "web_fetch"],
        max_turns=15,
        description="Read-only code review with structured feedback",
    ),
    "code-writer": SubagentPreset(
        name="code-writer",
        system_prompt=(
            "You are a professional code writing specialist. Implement requested "
            "changes with precision and verify your work.\n\n"
            "Coding principles:\n"
            "1. Minimal changes: only modify code necessary for the task\n"
            "2. Secure coding: avoid OWASP Top 10 vulnerabilities (injection, XSS, etc.)\n"
            "3. Style consistency: match surrounding code for naming, indentation, structure\n"
            "4. Thorough verification: run tests or checks after every change\n\n"
            "Workflow:\n"
            "1. Read relevant code to understand context\n"
            "2. Plan minimal modifications\n"
            "3. Execute code changes\n"
            "4. Verify: run tests, lint, type checks as appropriate\n"
            "5. Output a summary: what changed, why, and verification results"
        ),
        allowed_tools=["read_file", "write_file", "edit_file", "list_dir", "search", "exec"],
        max_turns=20,
        description="Code writing and modification with post-change verification",
    ),
    "researcher": SubagentPreset(
        name="researcher",
        system_prompt=(
            "You are an information research specialist. Your job is to search, "
            "collect, and synthesize information from web and local sources.\n\n"
            "You MUST NOT modify any files or execute any commands.\n\n"
            "Workflow:\n"
            "1. Analyze the research question and identify key information needs\n"
            "2. Use web_search to find relevant resources\n"
            "3. Use web_fetch to read key pages in depth\n"
            "4. Use search/read_file to consult local documentation\n"
            "5. Cross-reference findings from multiple sources\n\n"
            "Output a structured report with:\n"
            "- Summary: concise answer to the research question\n"
            "- Key findings: numbered list of discoveries with source attribution\n"
            "- Sources: list of URLs and file paths consulted"
        ),
        allowed_tools=["web_search", "web_fetch", "search", "read_file", "list_dir"],
        max_turns=25,
        description="Web research and information synthesis (read-only)",
    ),
}


def merge_presets(
    user_presets: list[dict],
) -> dict[str, SubagentPreset]:
    """Merge user-config presets over built-in presets.

    - Matching names override the corresponding built-in preset.
    - New names add additional preset types.
    - Returns the complete merged dictionary.
    """
    result = dict(BUILTIN_PRESETS)
    for cfg in user_presets:
        preset = SubagentPreset(
            name=cfg["name"],
            system_prompt=cfg.get("system_prompt", ""),
            allowed_tools=cfg.get("allowed_tools", []),
            max_turns=cfg.get("max_turns", 10),
            description=cfg.get("description", ""),
        )
        # For overrides, fill in missing fields from builtin if available
        if preset.name in result:
            builtin = result[preset.name]
            if not preset.system_prompt:
                preset.system_prompt = builtin.system_prompt
            if not preset.allowed_tools and not cfg.get("allowed_tools"):
                preset.allowed_tools = builtin.allowed_tools
            if not preset.description:
                preset.description = builtin.description
        result[preset.name] = preset
    return result
