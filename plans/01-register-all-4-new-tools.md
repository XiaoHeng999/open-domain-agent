# 01: Register All 4 New Tools

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Make `scan_builtin_tools` accept `**runtime_kwargs` so that `SelfTool`, `SandboxControlTool`, `MCPClientTool`, and `SearchTool` receive their required runtime dependencies. Wire registration in `AgentRuntime.on_start` after all subsystems are initialized. Ensure `agent tool list` CLI command displays all 4 new tools alongside existing ones.

## Acceptance criteria

- [ ] `scan_builtin_tools(**runtime_kwargs)` registers SelfTool, SandboxControlTool, MCPClientTool, SearchTool when runtime_kwargs are provided
- [ ] `AgentRuntime.on_start` calls `scan_builtin_tools` with runtime, sandbox, mcp_manager references
- [ ] `agent tool list` CLI command shows all 4 new tools in output
- [ ] Test: all 4 tools appear in registry after `scan_builtin_tools` with runtime kwargs
- [ ] Test: `agent tool list` output contains each new tool name

## User stories covered

- US 1: Agent developer sees all implemented tools auto-registered at startup
- US 2: `scan_builtin_tools` accepts runtime reference for dependency injection
- US 3: CLI user sees all available tools including the 4 new ones

## Blocked by

None — can start immediately
