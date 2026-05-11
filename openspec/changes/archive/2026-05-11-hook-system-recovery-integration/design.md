## Context

open_agent 采用 ReAct 循环（Thought → Action → Observation）驱动工具调用。当前 `_execute_action()` 中的错误处理仅将 `ToolError` 转为字符串，未调用已完整实现的 `recovery/` 模块。同时，框架缺少统一的 Hook 机制——前置安全检查硬编码在 `ToolRegistry.execute()` 的 Stage 3，staleness 提醒硬编码在 `_execute_action()` 中，无法被用户扩展。

代码风格约定：`dataclass` + `Enum` 模式（参考 `errors.py`、`strategies.py`），异步接口（参考 `Tool.execute()`），构造函数注入（参考 `ReActLoop.__init__`）。

## Goals / Non-Goals

**Goals:**
- 提供统一的 Hook 生命周期框架，支持 `SESSION_START`、`TOOL_BEFORE`、`TOOL_AFTER` 三种事件
- Hook 输出通过 `content` 字段注入到 LLM message 流中
- `TOOL_BEFORE` Hook 支持 `blocked=True` 阻止工具执行
- 将 `recovery/` 模块接入 `_execute_action()` 异常处理，使恢复策略自动生效
- 向后兼容：HookManager 为可选注入，不传入时行为不变

**Non-Goals:**
- 不实现 Hook 的持久化存储或跨会话复用
- 不实现 Hook 的配置文件声明式定义（仅代码注册）
- 不改变现有的 SafetyManager 和 ToolRegistry 执行管线
- 不实现 Hook 热重载

## Decisions

### 1. Hook 作为独立模块，不侵入 ToolRegistry

Hook 事件在 `ReActLoop._execute_action()` 中触发，而非在 `ToolRegistry.execute()` 内部。理由：ToolRegistry 是通用执行引擎，不应感知 Hook 概念；ReAct 循环是编排层，适合做生命周期管理。

### 2. HookResult.content 注入到 tool_result message

`TOOL_BEFORE` 和 `TOOL_AFTER` 的 `content` 字段通过前缀/后缀方式拼接到 tool_result message 的 content 中。这确保 LLM 能看到 Hook 输出的上下文，同时不改变消息格式。`SESSION_START` 的 content 注入到首次对话的 system message 末尾。

### 3. 恢复系统在异常分支调用

在 `_execute_action()` 的 `except ToolError` 分支中调用 `execute_recovery_chain()`，传入 `tool_registry`、`args`、`tool_handler` 作为 context。成功则用恢复结果替换原始错误；失败则保留错误信息但附带恢复 trace 摘要。

### 4. 优先级排序的注册机制

`HookManager.register()` 接受 `priority` 参数（数值越小越先执行），同优先级按注册顺序。`TOOL_BEFORE` 链中任一 Hook 返回 `blocked=True` 即中断执行。

### 5. 欢迎信息使用 HELLO! LUCKY! 图案

会话开始时在 terminal 打印 `HELLO! LUCKY!` ASCII 图案（由字符画组成），同时将纯文本版本注入 system message。

## Risks / Trade-offs

- **Hook 执行增加延迟**: 每个 Hook 是 `async` 调用，TOOL_BEFORE/TOOL_AFTER 会在每次工具调用时触发。缓解：内置 Hook 保持轻量（<1ms），用户自定义 Hook 需自行控制耗时。
- **Recovery 重试延长循环**: ServiceRecoveryStrategy 有 3 次指数退避（0.1s + 0.2s + 0.4s = 0.7s），加上 fallback tool 查找。缓解：总耗时远小于 LLM 调用延迟，可接受。
- **blocked Hook 导致工具不可用**: 用户可通过配置禁用特定 Hook。HookManager 构造时接受 `enabled` 参数。
