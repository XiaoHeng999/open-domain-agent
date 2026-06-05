# 03: Block Symlink-Based Path Traversal

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Change `_resolve_path` in `filesystem.py` from `os.path.abspath` to `os.path.realpath` so that symlinks are resolved before workspace boundary checks. This closes a path traversal attack where a symlink inside the workspace points to a file outside it.

## Acceptance criteria

- [ ] `filesystem.py:_resolve_path` uses `os.path.realpath` instead of `os.path.abspath`
- [ ] Test: symlink pointing outside workspace is rejected by boundary check
- [ ] Test: legitimate paths inside workspace still resolve correctly
- [ ] Test: existing filesystem tool tests pass unchanged

## User stories covered

- US 5: Path resolution follows symlinks before workspace boundary check

## Blocked by

None — can start immediately
