# 07: Parallel Tool Execution

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

When the LLM returns multiple tool calls in a single turn, execute them in parallel using `asyncio.gather`. Append `_tool_messages` in the original action order after all complete, so that the message sequence remains deterministic regardless of execution order.

## Acceptance criteria

- [ ] `ReActLoop._execute_action` dispatches multiple tool calls via `asyncio.gather`
- [ ] Tool results are appended in original action order, not completion order
- [ ] Test: two independent tool calls (e.g., read two files) execute and return correct ordered results
- [ ] Test: error in one parallel tool call does not cancel the other
- [ ] Test: single tool call path still works correctly

## User stories covered

- US 10: Multiple tool calls in one turn execute in parallel

## Blocked by

None — can start immediately
