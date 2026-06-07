# 10: Dead Code & Duplicate Implementation Cleanup

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Remove all unused dead code and resolve the `SubagentTool` duplicate. This is the largest slice and should be done last to minimize merge conflicts with other slices.

Delete the following unused code:

**Backward-compat modules never called by runtime:**
- `WorkingMemory` class and `create_working_memory()` factory method
- `EpisodicStore` class and `create_episodic_store()` factory method
- `UserProfileState` class and `create_user_profile()` factory method
- `SemanticKB` abstract class, `InMemorySemanticKB`, `create_semantic_kb()` factory (stub that always returns `[]`)
- Entire `memory/semantic.py` file

**Unused ABCs and data classes in `base.py`:**
- `ToolExecutor`, `IntentRecognizer`, `Router`, `LifecycleState`

**Unused agent/routing code:**
- `Reflection` dataclass in `react.py`
- `Plan.current_step()` and `is_complete()` in `planner.py`
- `RoutingPipeline.evaluate()`, `get_routing_trace()`, `RoutingTraceData` in `router.py`

**Unused monitoring code:**
- `TraceCollector.collect_trace()` and `query_live_spans()`
- `SkillMatcher.cleanup()`

**Duplicate implementation:**
- Delete `subagent/tool.py` entirely — runtime uses `tools/subagent.py`
- Remove `SubagentTool` export from `subagent/__init__.py`

**Misc:**
- `TODO_TOOL_SCHEMA` constant in `todo.py` (duplicates `TodoTool.parameters`)
- Unused `_ptk_prompt` import in `cli.py`
- Hardcoded Chinese text in `runtime.py` `_missing_slots_hint` → change to English
- `generate_clarification()` call in `runtime.py` (result discarded)
- Empty `provider/` directory

Update all `__init__.py` files and `__all__` lists to remove deleted exports.

## Acceptance criteria

- [ ] All listed dead code removed from source files
- [ ] `memory/semantic.py` file deleted
- [ ] `subagent/tool.py` file deleted
- [ ] `provider/` empty directory deleted
- [ ] All `__init__.py` and `__all__` updated to remove deleted exports
- [ ] No `ImportError` or `AttributeError` from `from open_agent.memory import *` or `from open_agent.subagent import *`
- [ ] `pytest tests/ -x -q` passes — all existing tests still pass after cleanup
- [ ] `make check` passes

## User stories covered

- US 12: All unused dead code removed, reducing cognitive load
- US 13: `SubagentTool` has only one implementation

## Blocked by

- Issues 01-09 should complete first to minimize merge conflicts (this slice touches many of the same files)
