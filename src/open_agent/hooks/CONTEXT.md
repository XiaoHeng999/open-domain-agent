# hooks/ — 生命周期 Hook 系统

- `types.py` — HookEvent（SESSION_START/TOOL_BEFORE/TOOL_AFTER）、HookResult、HookCallback
- `manager.py` — HookManager：优先级排序、链式执行、blocked 短路
- `builtin.py` — 内置 hook：welcome（横幅）、pre_check（危险命令阻断）、audit（审计日志）
