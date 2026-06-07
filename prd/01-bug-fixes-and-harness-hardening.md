# PRD-01: Bug Fixes & Harness Hardening

## Problem Statement

The open-agent framework has accumulated implementation gaps and bugs that prevent it from functioning as a production-grade coding agent harness. Critical tools are implemented but never registered, security vulnerabilities exist in sandbox execution, dead code paths waste development and runtime resources, and several architectural loops (feedback, caching, validation) are incomplete or broken. The harness also lacks essential capabilities for a coding agent: streaming output, cost tracking, conversation persistence, task cancellation, and prompt caching.

## Solution

Fix all identified bugs, close all broken loops, and add the missing harness capabilities to bring open-agent to a production-ready state. The work is split into two phases:

1. **Phase 1 — Bug Fixes & Security** (11 items): Fix tool registration gaps, security vulnerabilities, dead code paths, and incomplete implementations.
2. **Phase 2 — Harness Capabilities** (8 items): Add streaming, persistence, cost tracking, cancellation, caching, and other capabilities expected of a production coding agent.

## User Stories

### Tool Registration & Discovery

1. As an agent developer, I want all implemented tools (SelfTool, SearchTool, SandboxControlTool, MCPClientTool) to be automatically registered during startup, so that the LLM can discover and use them.
2. As an agent developer, I want `scan_builtin_tools` to accept a runtime reference for dependency injection, so that tools requiring runtime state (SelfTool, SandboxControlTool, MCPClientTool) can be properly wired.
3. As a CLI user, I want `agent tool list` to show all available tools including the 4 new ones, so that I can verify tool availability.

### Safety & Security

4. As an agent operator, I want Docker sandbox commands to be passed as argument lists instead of shell-interpolated strings, so that command injection via quote escaping is prevented.
5. As an agent operator, I want filesystem path resolution to follow symlinks before checking workspace boundaries, so that symlink-based path traversal attacks are blocked.
6. As an agent operator, I want SelfTool to not declare a `safety_checks` type that no middleware handles, so that safety declarations are accurate.
7. As an agent operator, I want MCPClientTool to declare `safety_checks = ["url"]` instead of `["command"]`, so that MCP server startup commands are not incorrectly flagged as dangerous shell commands.

### Middleware & Execution Pipeline

8. As an agent developer, I want `validate_output()` to be called on every tool execution regardless of whether `output_schema` is set, so that output validation checks actually run.
9. As an agent developer, I want read-only tool results to be cached in the RuntimeMemory LRU cache, so that repeated identical tool calls avoid redundant execution and token waste.
10. As an agent developer, I want multiple tool calls returned by the LLM in a single turn to execute in parallel via `asyncio.gather`, so that independent operations (e.g., reading two files) complete faster.
11. As an agent developer, I want `_tool_messages` to be managed by RuntimeMemory instead of ReActLoop internal state, so that context window overflow protection is unified and token budgets are enforced.

### Provider Layer

12. As an agent developer, I want the Anthropic provider to pass `temperature` to all API calls (`complete`, `complete_with_tools`), so that behavior matches the OpenAI provider.
13. As an agent developer, I want all provider API calls to automatically retry on transient errors (429, 502, 503, network timeout) with exponential backoff via tenacity, so that transient API failures don't terminate the entire agent loop.

### HITL & Permissions

14. As an agent operator, I want `HITLApprovalManager.approve` to be an async method, so that interactive user approval does not block the asyncio event loop during multi-agent or streaming scenarios.

### Answer Quality & Feedback

15. As an end user, I want the agent to generate a human-readable summary of its work after completing all tool steps, so that I receive a clear final answer instead of raw tool output.
16. As an agent developer, I want the FeedbackLoop's avoidance hints to be injected into the system prompt via ProfileMemory, so that the agent learns from past failures across sessions.

### Conversation Persistence

17. As an end user, I want conversation history to persist across process restarts via SQLite, so that I can resume sessions and the agent maintains long-term context.
18. As an agent operator, I want conversation records older than 7 days to be automatically cleaned up, so that storage does not grow unbounded.

### Streaming Output

19. As an end user, I want to see the LLM's thinking streamed in real-time during the ReAct loop, so that I know the agent is actively working.
20. As an end user, I want long-running tool executions (exec, web fetch) to show intermediate progress, so that I am not left waiting without feedback.

### Cost Tracking

21. As an agent operator, I want per-request token usage (input/output) to be recorded from API responses, so that I can track resource consumption.
22. As an agent operator, I want a CostTracker that aggregates token usage by model and date, applies per-model pricing, and exposes daily/weekly summaries and budget alerts, so that I can control API spending.

### Prompt Caching

23. As an agent operator, I want the Anthropic provider to mark system prompts and tool definitions with `cache_control`, so that repeated context across ReAct iterations reduces token consumption.
24. As an agent developer, I want a `caching: bool = True` config option to toggle prompt caching, so that I can disable it for debugging or providers that don't support it.

### Task Cancellation

25. As an end user in chat mode, I want to press ESC to cancel the currently running agent task, so that I can stop long-running operations without terminating the entire process.
26. As an agent developer, I want a CancellationToken (asyncio.Event) checked at each ReAct iteration boundary, so that cancellation is graceful and does not corrupt state.

### Eval System

27. As an agent developer, I want a minimal eval runner that loads YAML test scenarios and executes them against AgentRuntime, so that I can run smoke tests to verify agent behavior.
28. As an agent developer, I want the CLI `agent eval` command to invoke the eval runner and display pass/fail results, so that regression testing is accessible from the command line.

### CLI Improvements

29. As an end user in chat mode, I want async input handling (via prompt_toolkit or similar) instead of blocking `input()`, so that the event loop remains responsive during streaming and cancellation.

## Implementation Decisions

### Tool Registration Refactor

- `scan_builtin_tools` will accept an optional `**runtime_kwargs` parameter for dependency injection.
- `SelfTool` requires `react_loop` and `runtime` references (weakref internally).
- `SandboxControlTool` requires `sandbox` instance.
- `MCPClientTool` requires `mcp_manager` instance.
- `SearchTool` requires `workspace` string (same as existing filesystem tools).
- Registration happens in `AgentRuntime.on_start` after all subsystems are initialized.

### Docker Sandbox Security

- `DockerSandbox.exec` will use `exec_run(cmd=["bash", "-c", command])` or better, pass the command as a list to avoid shell interpolation entirely.
- `DockerSandbox.write_file` will use tar/archive API (similar to existing `read_file`) instead of heredoc shell commands.

### Middleware Pipeline Changes

- `OutputValidationMiddleware.process` will call `validate_output()` unconditionally (outside the `if schema is not None` block).
- `ToolRegistry.execute` will check RuntimeMemory cache before running the middleware chain for `read_only` tools. Cache is populated on successful execution.
- Parallel tool execution in `ReActLoop._execute_action` loop will use `asyncio.gather`, with `_tool_messages` appended in original action order after all complete.

### RuntimeMemory Unified Management

- `_tool_messages` (tool_use/tool_result pairs) will be stored in RuntimeMemory instead of ReActLoop internals.
- RuntimeMemory will enforce token budget across all message types (conversation + tool messages + summary).
- When budget is exceeded, oldest tool_result messages will be compressed/truncated first (they are the largest).

### Provider Layer

- Anthropic provider `complete` and `complete_with_tools` will pass `temperature=kwargs.get("temperature", self.config.temperature)`.
- All provider API calls will be wrapped with `tenacity.retry` targeting transient HTTP errors (429, 502, 503, connection timeouts), max 3 retries, exponential backoff (1s, 2s, 4s).

### HITL Async Interface

- `HITLApprovalManager.approve` signature changes from `def approve(...) -> ApprovalResult` to `async def approve(...) -> ApprovalResult`.
- All callers (PermissionMiddleware, PermissionGuard) updated to `await` the call.

### Final Answer Summary

- After ReAct loop completes, a single summary LLM call will be made with all step thought/action/observation summaries.
- Uses short `max_tokens` (256) to control cost.
- Summary replaces the raw tool output as the final answer.

### Feedback Loop Closure

- `PromptBuilder` or `_build_messages` will read avoidance hints from `ProfileMemory` and inject them into the system prompt.
- Hints will be specific (tool name, error pattern, suggested alternative).

### Conversation Persistence

- `RuntimeMemory` will get an optional SQLite backend activated by config.
- `add_message` writes to both in-memory buffer and SQLite (async via `asyncio.to_thread`).
- On startup, load last N messages from SQLite.
- A background task or startup hook will delete records older than 7 days.
- Schema: `messages(id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)`.

### Streaming Architecture

- Provider layer: add `stream=True` support to `complete_with_tools`, yielding partial text chunks.
- ReActLoop: thought text streams to a callback/emitter as it arrives.
- Tool execution: long-running tools emit progress via an `on_progress` callback.
- CLI: use `prompt_toolkit` for async input that doesn't block the event loop.

### Cost Tracking

- `ToolCallResponse` gains a `usage: dict[str, int] | None` field (input_tokens, output_tokens).
- Each provider extracts usage from the raw API response and populates it.
- A `CostTracker` class accumulates per-model, per-day usage with configurable pricing.
- Exposes `get_daily_summary()`, `get_weekly_summary()`, `check_budget(limit)`.
- Integrated into `AgentRuntime.run` to record usage after each iteration.

### Prompt Caching

- Anthropic provider: system message and tool definitions get `cache_control: {"type": "ephemeric"}` markers.
- Config: `AgentConfig` gains `caching: bool = True`.
- Only applied when `caching=True` and provider is Anthropic.

### Task Cancellation

- `CancellationToken` wraps an `asyncio.Event`.
- Passed into `ReActLoop.run`, checked at each iteration boundary.
- CLI chat mode: ESC key press sets the event (via `prompt_toolkit` key bindings).
- Sub-agent cancellation uses the same token pattern.

### Eval Runner

- Minimal YAML scenario format: `name`, `input`, `expected_tools` (optional), `expected_outcome` (optional).
- `EvalRunner` loads scenarios, calls `AgentRuntime.run`, checks assertions.
- CLI `agent eval --suite smoke` runs scenarios from a configurable directory.

### Path Security

- `filesystem.py:_resolve_path` switches from `os.path.abspath` to `os.path.realpath` to resolve symlinks before workspace boundary check.

## Testing Decisions

### Testing Philosophy

- Test external behavior, not implementation details.
- Prefer integration tests over mocked unit tests where feasible.
- Use the existing `pytest + pytest-asyncio` framework with `asyncio_mode=auto`.

### Test Modules

| Module | Test Focus |
|--------|-----------|
| `tests/test_tool_registration.py` | Verify all 4 new tools appear in registry after `scan_builtin_tools` with runtime kwargs |
| `tests/test_safety_risk.py` (extend) | Symlink traversal blocked, MCPClientTool no false positive on command check |
| `tests/test_docker_injection.py` (extend) | Command injection payloads return errors, not arbitrary execution |
| `tests/test_middleware_chain.py` (extend) | `validate_output` runs without `output_schema`; cache hit skips chain for read-only tools |
| `tests/test_react_tool_use.py` (extend) | Parallel tool execution produces correct ordered results; cancellation token stops loop |
| `tests/test_provider_tools.py` (extend) | Anthropic provider passes temperature; retry fires on 429/503 |
| `tests/test_permission_integration.py` (extend) | Async `approve` works with `await` |
| `tests/test_layered_memory.py` (extend) | SQLite persistence round-trip; 7-day cleanup; tool messages managed by RuntimeMemory |
| `tests/test_streaming.py` (new) | LLM thought streaming callback receives chunks; tool progress callback fires |
| `tests/test_cost_tracking.py` (new) | Usage extracted from provider responses; CostTracker aggregates correctly |
| `tests/test_prompt_caching.py` (new) | Anthropic requests include cache_control markers |
| `tests/test_eval.py` (extend) | YAML scenarios load and run; pass/fail reported |

### Prior Art

- Existing tests use `AsyncMock` for providers and `tmp_path` for filesystem tests.
- Tool registration tests follow the pattern in `test_tool_registry_v2.py`.
- Middleware tests follow `test_middleware_chain.py` pattern.
- Memory tests follow `test_layered_memory.py` and `test_memory.py` patterns.

## Out of Scope

- **Multi-modal support** (images, screenshots) — future PRD.
- **GitTool** — not needed; ExecTool whitelist enhancement is sufficient.
- **LSP/code intelligence integration** — future PRD.
- **Automatic project context loading** (reading CLAUDE.md, package.json) — future PRD.
- **Distributed/multi-node execution** — out of scope for single-machine agent.
- **User authentication/authorization** — out of scope for local CLI agent.
- **Web UI / API server** — future PRD.

## Further Notes

### Priority Order

Phase 1 (bugs/security) should be completed before Phase 2 (capabilities). Within Phase 1, security issues (Docker injection, symlink traversal) are highest priority, followed by functional bugs (tool registration, dead code), followed by optimizations (caching, parallel execution).

### Dependency Graph

Several Phase 2 items have dependencies:
- **Streaming** requires async CLI input (prompt_toolkit).
- **Task cancellation** (ESC key) also requires async CLI input.
- **Cost tracking** requires provider usage extraction, which touches the same provider code as **retry** and **prompt caching**.
- **`_tool_messages` in RuntimeMemory** should be done before **streaming** to avoid merge conflicts.

### Config Additions

New config fields needed in `AgentConfig`:
- `caching: bool = True` — prompt caching toggle.
- `persistence.enabled: bool = False` — conversation persistence toggle.
- `persistence.db_path: str` — SQLite path.
- `persistence.retention_days: int = 7` — auto-cleanup period.
- `cost_tracking.enabled: bool = True` — cost tracking toggle.
- `cost_tracking.budget_daily: float | None` — optional daily budget limit.
