"""Centralized prompt template constants.

All prompt text used by the Prompt Pipeline lives here so that
tuning prompts only requires editing this single file.
"""

# ── Segment separator ──
SEGMENT_SEPARATOR = "\n\n---\n\n"

# ── Segment tag names (used as XML-style markers) ──
SEGMENT_TAG_CORE_IDENTITY = "core_identity"
SEGMENT_TAG_TOOL_LIST = "tool_list"
SEGMENT_TAG_SKILLS = "skills"
SEGMENT_TAG_MEMORY = "memory"
SEGMENT_TAG_CLAUDEMD = "claudemd"
SEGMENT_TAG_DYNAMIC_ENV = "dynamic_env"

# ── Core Identity ──
CORE_IDENTITY_TEMPLATE = """You are {agent_name}, an autonomous agent built on the open-agent framework.

Core capabilities:
- Reason through tasks using the ReAct (Thought → Action → Observation) cycle
- Use available tools to interact with the environment
- Plan multi-step strategies when tasks are complex
- Learn from observations and adapt your approach

Behavioral guidelines:
- Be concise and precise in your reasoning
- Prefer tool usage over speculation
- Report errors transparently
- Respect safety boundaries and workspace constraints"""

CORE_IDENTITY_CUSTOM_TEMPLATE = """{custom_identity}"""

# ── Tool List ──
TOOL_LIST_HEADER = "Available tools:"
TOOL_ENTRY_TEMPLATE = """- {name}: {description}
  Parameters: {parameters}"""

# ── Skills ──
SKILLS_HEADER = "Active skills:"
SKILL_ENTRY_TEMPLATE = """## {name}
{content}"""

# ── Memory ──
MEMORY_HEADER = "Context memory:"
MEMORY_WORKING_TEMPLATE = """### Current conversation
{working_memory}"""
MEMORY_EPISODIC_TEMPLATE = """### Relevant history
{episodic_summary}"""
MEMORY_PROFILE_TEMPLATE = """### User preferences
{user_profile}"""

# ── CLAUDE.md ──
CLAUDEMD_HEADER = "Project directives:"

# ── Dynamic Environment ──
DYNAMIC_ENV_TEMPLATE = """Current environment:
- Date: {date}
- Platform: {platform}
- Working directory: {workdir}"""
