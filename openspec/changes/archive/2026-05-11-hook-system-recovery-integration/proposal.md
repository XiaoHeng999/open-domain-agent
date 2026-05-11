## Why

ReAct 循环中的工具错误处理目前仅将异常转为字符串返回给 LLM，未调用已完整实现的 recovery 模块（`recovery/` 目录下的 classifier、strategies、engine）。同时，框架缺少统一的 Hook 机制来支持会话生命周期事件（如会话开始欢迎、工具执行前后拦截/审计），现有硬编码的 staleness 检查和 safety check 无法被用户自定义扩展。

## What Changes

- 新增 `src/open_agent/hooks/` 模块：定义 `HookEvent` 枚举、`HookCallback` 类型、`HookResult` 数据结构和 `HookManager` 注册/触发引擎
- 新增 3 个内置 Hook：会话开始欢迎信息（HELLO! LUCKY! 图案）、工具执行前额外检查、工具执行后审计日志
- 将 Hook 机制接入 `ReActLoop._execute_action()`：在工具执行前触发 `TOOL_BEFORE`（支持阻止执行），执行后触发 `TOOL_AFTER`（审计 + 注入 message）
- 将 Hook 机制接入 `AgentRuntime.on_start()`：触发 `SESSION_START` 事件，输出欢迎信息
- 将已有 recovery 模块接入 `_execute_action()` 的异常处理分支：ToolError 发生时调用 `execute_recovery_chain()`，成功则使用恢复结果，失败则 escalate
- Hook 输出内容通过 `content` 字段注入到 LLM message 流中（tool_result message）

## Capabilities

### New Capabilities

- `hook-system`: 统一的 Hook 生命周期框架，支持 SESSION_START / TOOL_BEFORE / TOOL_AFTER 三种事件，HookManager 注册/触发机制，HookResult 注入到 message 流

### Modified Capabilities

- `tool-error-recovery`: 将 recovery 模块接入 ReAct 循环，从独立库变为运行时自动调用的恢复链

## Impact

- **新增文件**: `src/open_agent/hooks/__init__.py`, `hooks/types.py`, `hooks/manager.py`, `hooks/builtin.py`
- **修改文件**: `src/open_agent/agent/react.py`（接入 hook + recovery）, `src/open_agent/runtime.py`（初始化 HookManager + 注册内置 hooks）
- **配置**: `AgentConfig` 新增 `hooks` 配置块（启用/禁用开关）
- **向后兼容**: HookManager 为可选注入，不传入时行为与改动前完全一致
