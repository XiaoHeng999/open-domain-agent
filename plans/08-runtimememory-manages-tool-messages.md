# 08: RuntimeMemory Manages Tool Messages

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Move `_tool_messages` (tool_use/tool_result pairs) from `ReActLoop` internal state to `RuntimeMemory`. RuntimeMemory enforces the token budget across all message types (conversation + tool messages + summary). When budget is exceeded, oldest tool_result messages are compressed/truncated first.

## Acceptance criteria

- [ ] `_tool_messages` stored in `RuntimeMemory` instead of `ReActLoop` internals
- [ ] `RuntimeMemory` enforces token budget across conversation + tool messages
- [ ] When budget exceeded, oldest tool_result messages are compressed first
- [ ] Test: tool messages round-trip through RuntimeMemory correctly
- [ ] Test: token budget overflow triggers compression of oldest tool results
- [ ] Test: existing ReActLoop tool execution tests pass unchanged

## User stories covered

- US 11: Context window overflow protection is unified via RuntimeMemory

## Blocked by

- Plan 07: Parallel Tool Execution (touches same ReActLoop._execute_action code)
