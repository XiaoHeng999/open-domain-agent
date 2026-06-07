# 01: Ghost Exports & Naming Collision Fixes

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix three P0 issues that can cause runtime crashes:

1. Remove `TokenEstimator` from `memory/__init__.py`'s `__all__` — this name was never defined or imported, causing `AttributeError` on `from open_agent.memory import TokenEstimator` or `from open_agent.memory import *`. The actual token estimation function `estimate_tokens()` in `token_utils.py` is fully implemented and widely used.

2. Rename `MemoryError` to `AgentMemoryError` in `errors.py` — the current name shadows Python's built-in `MemoryError`. Any code importing it will silently override the builtin. Search and update all references across the entire codebase (source and tests).

3. Delete `LocalProvider` from `model.py` and remove its registration in `ProviderFactory` — it returns a hardcoded string from `complete()` and lacks `complete_with_tools`, causing `NotImplementedError` when the ReAct loop runs with `provider: "local"` configured.

## Acceptance criteria

- [ ] `memory/__init__.py` `__all__` no longer contains `TokenEstimator`
- [ ] `errors.py` defines `AgentMemoryError` (not `MemoryError`)
- [ ] All imports and references to the old `MemoryError` name are updated to `AgentMemoryError` in source and tests
- [ ] `LocalProvider` class is deleted from `model.py`
- [ ] `ProviderFactory` no longer registers `"local"` provider
- [ ] `pytest tests/ -x -q` passes with no failures

## User stories covered

- US 4: User gets clear error when misconfiguring `provider: "local"`, not a runtime crash
- US 5: Custom error types don't shadow Python builtins

## Blocked by

None — can start immediately
