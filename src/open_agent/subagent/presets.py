"""Built-in sub-agent presets and merge logic."""

from __future__ import annotations

from open_agent.subagent.types import SubagentPreset

BUILTIN_PRESETS: dict[str, SubagentPreset] = {
    "explore": SubagentPreset(
        name="explore",
        system_prompt=(
            "You are a read-only code explorer. Your job is to search, read, and "
            "analyze code to answer questions. You MUST NOT modify any files or "
            "execute any commands. Only use read-only tools like read_file, list_dir, "
            "web_search, and web_fetch. Provide concise, accurate summaries."
        ),
        allowed_tools=["read_file", "list_dir", "web_search", "web_fetch"],
        max_turns=20,
        description="Read-only codebase exploration and information retrieval",
    ),
    "plan": SubagentPreset(
        name="plan",
        system_prompt=(
            "You are a planning agent. Analyze the task, explore relevant code and "
            "resources, then produce a structured step-by-step plan. You MUST NOT "
            "modify any files or execute commands. Focus on understanding the problem "
            "and designing a clear execution plan with numbered steps."
        ),
        allowed_tools=["read_file", "list_dir", "web_search", "web_fetch"],
        max_turns=15,
        description="Task analysis and structured plan generation",
    ),
    "general": SubagentPreset(
        name="general",
        system_prompt=(
            "You are a general-purpose sub-agent. Complete the assigned task using "
            "the tools available to you. Return a concise summary of your findings "
            "or actions as the final answer."
        ),
        allowed_tools=[],
        max_turns=10,
        description="General-purpose sub-agent with full tool access",
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
