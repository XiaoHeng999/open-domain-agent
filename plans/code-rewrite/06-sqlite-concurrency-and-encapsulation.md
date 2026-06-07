# 06: SQLite Concurrency & Encapsulation Fix

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix two related issues around memory subsystem robustness:

1. **SQLite concurrency**: `RuntimeMemory` uses `check_same_thread=False` for its SQLite connection and runs `_persist_message` via `asyncio.to_thread`, but has no mutex protecting concurrent writes. Add a `threading.Lock` and acquire it around all SQLite write operations.

2. **Private attribute access**: Runtime accesses `_runtime_memory._messages` and `checkpoint_manager._storage` directly, breaking encapsulation. Add public methods:
   - `RuntimeMemory.get_recent_messages(n: int)` — returns the last n messages
   - `CheckpointManager.close_storage()` — closes the underlying storage connection
   Update runtime to call these public methods instead of reaching into private attributes.

3. **assert guards**: `ProfileMemory` uses `assert self._conn` for null checks, which are stripped under `python -O`. Replace with `if not self._conn: raise RuntimeError(...)`.

## Acceptance criteria

- [ ] `RuntimeMemory` has a `threading.Lock` protecting SQLite write operations
- [ ] `RuntimeMemory.get_recent_messages(n)` public method exists and works correctly
- [ ] `CheckpointManager.close_storage()` public method exists and works correctly
- [ ] Runtime calls public methods instead of `._messages` and `._storage`
- [ ] `ProfileMemory` uses `if` guards instead of `assert` for connection null-checks
- [ ] Existing tests pass (`test_checkpoint_sqlite_default.py`, `test_checkpoint.py`, `test_checkpoint_integration.py`, `test_layered_memory.py`)

## User stories covered

- US 11: `_glob` search has result count limit
- US 16: Runtime doesn't access private attributes of other components

## Blocked by

None — can start immediately
