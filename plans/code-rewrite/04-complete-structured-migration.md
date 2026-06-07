# 04: complete_structured → complete_with_tools Migration

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Complete the migration from `complete_structured` to `complete_with_tools` across the entire codebase. All three providers emit `DeprecationWarning` in `complete_structured`, yet 8+ call sites still use it — warnings fire during normal operation.

Migrate all callers to use `complete_with_tools` with an empty tools list or appropriate tool definitions. Then remove `complete_structured` from all provider classes and the base interface.

Callers to migrate:
- Routing complexity classifier
- Routing domain router
- Routing unified LLM router
- Routing intent parser
- Agent ReAct loop (fallback path)
- Agent planner
- Eval judge

## Acceptance criteria

- [ ] All 8+ call sites use `complete_with_tools` instead of `complete_structured`
- [ ] `complete_structured` method is removed from all provider classes and base interface
- [ ] No `DeprecationWarning` fires during normal operation
- [ ] Routing tests pass (`test_unified_routing.py`, `test_routing.py`, `test_fast_path.py`)
- [ ] Agent tests pass (`test_agent.py`, `test_react_tool_use.py`)
- [ ] Eval tests pass (`test_eval.py`, `test_llmjudge.py`)

## User stories covered

- US 14: All LLM calls use the unified `complete_with_tools` interface, eliminating deprecation warnings

## Blocked by

None — can start immediately
