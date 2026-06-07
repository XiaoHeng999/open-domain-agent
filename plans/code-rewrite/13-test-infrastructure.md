# 13: Test Infrastructure

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix three structural test issues:

1. **Create `tests/conftest.py`** with shared fixtures to eliminate duplication across 10+ test files:
   - `mock_provider` — returns a configurable mock LLM provider
   - `tool_registry` — pre-registered `ToolRegistry` with common tools
   - `routing_decision` — `RoutingDecision` with sensible defaults
   - `safety_manager` — `SafetyManager` instance
   - `permission_guard` — `PermissionGuard` instance

2. **Add test markers and coverage config** to `pyproject.toml`:
   - Register markers: `slow`, `integration`, `unit`
   - Add `[tool.coverage]` section with source and report paths

3. **Delete empty test**: Remove `test_no_runtime_memory_graceful` in `test_runtime_memory_tool_messages.py` which contains only `pass` and validates nothing.

## Acceptance criteria

- [ ] `tests/conftest.py` exists with all 5 shared fixtures
- [ ] `pyproject.toml` registers `slow`, `integration`, `unit` markers
- [ ] `pyproject.toml` has coverage configuration
- [ ] `test_no_runtime_memory_graceful` placeholder test removed
- [ ] `pytest tests/ -x -q` passes — existing tests work with new conftest
- [ ] At least 3 existing test files updated to use shared fixtures (validate the fixtures work)

## User stories covered

- US 20: Tests have shared conftest.py to reduce fixture duplication
- US 21: Coverage configuration exists for measuring test quality
- US 22: No placeholder tests that validate nothing

## Blocked by

- Issues 01-10 should complete first — test infrastructure should be stable when code changes are done
