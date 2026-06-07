# 02: Sandbox Async & Lifecycle Fix

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix two related sandbox issues:

1. **Event loop blocking**: `DaytonaSandbox.read_file()` and `write_file()` call synchronous SDK methods directly inside `async def`. `DockerSandbox` has the same problem in `exec()`, `read_file()`, and `write_file()` — all call the synchronous Docker SDK inside `async def` without `asyncio.to_thread`. This freezes the entire event loop during sandbox I/O. Wrap all synchronous SDK calls with `asyncio.to_thread()`, following the pattern already used by `DaytonaSandbox.exec()`.

2. **Lifecycle gap**: `SandboxFactory.create()` returns a sandbox instance without calling `on_start()`, and the runtime never explicitly calls it either. This means `_workspace`/`_container` may be `None` when tools try to use the sandbox. Add an explicit `await sandbox.on_start()` call in the runtime's `on_start()` method, after the sandbox is created but before tools are registered.

## Acceptance criteria

- [ ] `DaytonaSandbox.read_file()` and `write_file()` wrap sync SDK calls with `asyncio.to_thread()`
- [ ] `DockerSandbox.exec()`, `read_file()`, `write_file()` wrap sync Docker SDK calls with `asyncio.to_thread()`
- [ ] Runtime's `on_start()` calls `await sandbox.on_start()` when sandbox is configured
- [ ] No sync blocking calls remain in any sandbox `async def` method
- [ ] Existing sandbox tests pass (`test_docker_hardening.py`, `test_sandbox_injection.py`, `test_sandbox_timeout.py`, `test_docker_restore.py`)

## User stories covered

- US 6: Sandbox I/O operations don't block the event loop
- US 17: Sandbox is properly initialized before use

## Blocked by

None — can start immediately
