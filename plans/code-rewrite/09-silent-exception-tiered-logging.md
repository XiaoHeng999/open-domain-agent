# 09: Silent Exception Tiered Logging

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、生代码清理与功能补全

## What to build

Replace all bare `except ... pass` blocks across the codebase with tiered logging, so failures become diagnosable:

- **Critical paths** (config parsing, runtime initialization, checkpoint persistence) → `logger.warning(...)` — users should know when their config or runtime setup failed
- **Non-critical paths** (trace persistence, memory span creation, cleanup) → `logger.debug(...)` — useful for debugging but shouldn't spam normal operation

Locations to fix:
- `trace.py` — 5 bare `pass` handlers in persist/load/list operations
- `config.py` — silently swallowed JSON parse errors in env var override
- `cli.py` — swallowed runtime creation exception in eval command
- `runtime.py` — swallowed trace persistence exception in `on_stop()`

Add `import logging; logger = logging.getLogger(__name__)` where not already present.

## Acceptance criteria

- [ ] All `except ... pass` blocks in critical paths replaced with `logger.warning(...)`
- [ ] All `except ... pass` blocks in non-critical paths replaced with `logger.debug(...)`
- [ ] No bare `pass` exception handlers remain (except intentional fall-throughs in recovery strategies)
- [ ] `logging` module imported and logger created in all affected files
- [ ] Existing tests pass — logging does not change control flow

## User stories covered

- US 15: Critical path exceptions have at least warning-level logging

## Blocked by

None — can start immediately
