## ADDED Requirements

### Requirement: Hook 事件类型定义
系统 SHALL 定义三种 Hook 事件类型：`SESSION_START`（会话启动时触发一次）、`TOOL_BEFORE`（每次工具执行前触发）、`TOOL_AFTER`（每次工具执行后触发）。每种事件类型通过 `HookEvent` 枚举表示。

#### Scenario: HookEvent 枚举值完整
- **WHEN** 检查 `HookEvent` 枚举
- **THEN** 包含 `SESSION_START`、`TOOL_BEFORE`、`TOOL_AFTER` 三个成员

### Requirement: HookResult 数据结构
系统 SHALL 定义 `HookResult` 数据结构，包含 `content`（可选字符串，注入到 message 流）、`blocked`（布尔值，仅 TOOL_BEFORE 有效，为 True 时阻止工具执行）、`metadata`（字典，存储审计等非注入数据）。

#### Scenario: HookResult 默认值
- **WHEN** 创建 HookResult 未指定参数
- **THEN** content 为 None、blocked 为 False、metadata 为空字典

#### Scenario: blocked=True 阻止工具执行
- **WHEN** TOOL_BEFORE Hook 返回 HookResult(blocked=True, content="Blocked: requires confirmation")
- **THEN** 工具不执行，Observation 的 content 为 "Blocked: requires confirmation"，success 为 False

### Requirement: HookManager 注册与触发
系统 SHALL 提供 `HookManager` 类，支持通过 `register(event, callback, priority)` 注册 Hook 回调，通过 `fire(event, context)` 触发指定事件的所有回调。回调按 priority 升序执行（数值越小越先执行），同优先级按注册顺序。

#### Scenario: 按优先级顺序执行
- **WHEN** 注册 priority=10 的 Hook A 和 priority=5 的 Hook B 到 TOOL_BEFORE
- **THEN** fire(TOOL_BEFORE, {}) 先执行 B 再执行 A

#### Scenario: TOOL_BEFORE 链中 blocked 中断
- **WHEN** TOOL_BEFORE 有两个 Hook，第一个返回 blocked=True
- **THEN** 第二个 Hook 不执行，工具不执行

#### Scenario: fire 返回所有结果
- **WHEN** 三个 Hook 都返回 HookResult
- **THEN** fire 返回包含三个 HookResult 的列表

### Requirement: 会话开始欢迎信息 Hook
系统 SHALL 提供内置 `welcome_hook`，在 SESSION_START 事件触发时打印 HELLO! LUCKY! 字符图案到终端，并将简化文本版本通过 HookResult.content 返回以注入 system message。

#### Scenario: 欢迎信息输出
- **WHEN** AgentRuntime.on_start() 触发 SESSION_START
- **THEN** 终端打印 HELLO! LUCKY! 字符图案，且 HookResult.content 包含欢迎文本

### Requirement: 工具执行前检查 Hook
系统 SHALL 提供内置 `pre_check_hook`，在 TOOL_BEFORE 事件触发时执行额外安全验证。对高风险工具（ExecTool）要求参数中不含危险命令模式。

#### Scenario: 高风险工具检查通过
- **WHEN** ExecTool 调用参数 command="ls -la"
- **THEN** pre_check_hook 返回 HookResult(blocked=False)，工具正常执行

#### Scenario: 高风险工具检查阻止
- **WHEN** ExecTool 调用参数 command="rm -rf /"
- **THEN** pre_check_hook 返回 HookResult(blocked=True, content="Blocked: dangerous command pattern detected")

### Requirement: 工具执行后审计 Hook
系统 SHALL 提供内置 `audit_hook`，在 TOOL_AFTER 事件触发时记录工具名、执行结果（成功/失败）、耗时到 logger（INFO 级别），并将审计摘要通过 HookResult.content 返回以注入 tool_result message。

#### Scenario: 成功执行审计
- **WHEN** read_file 工具成功执行耗时 15ms
- **THEN** logger 输出 "[AUDIT] tool=read_file success=True duration=15.0ms"，HookResult.content 包含审计摘要

#### Scenario: 失败执行审计
- **WHEN** exec 工具执行失败（exit code 1）
- **THEN** logger 输出 "[AUDIT] tool=exec success=False duration=...ms"

### Requirement: Hook 输出注入到 message 流
系统 SHALL 将 TOOL_BEFORE 和 TOOL_AFTER 的 HookResult.content 以注释标签形式注入到 tool_result message 的 content 中。TOOL_BEFORE 的内容作为前缀，TOOL_AFTER 的内容作为后缀。

#### Scenario: TOOL_BEFORE 注入前缀
- **WHEN** TOOL_BEFORE Hook 返回 content="<pre-check>Verified</pre-check>"，工具返回 "File contents: ..."
- **THEN** tool_result message 的 content 为 "<pre-check>Verified</pre-check>\nFile contents: ..."

#### Scenario: 多 Hook content 合并
- **WHEN** TOOL_AFTER 有两个 Hook 分别返回 content="[AUDIT] ..." 和 "[METRIC] ..."
- **THEN** tool_result message 的 content 后缀为 "\n[AUDIT] ...\n[METRIC] ..."

### Requirement: HookManager 可选注入
HookManager 在 ReActLoop 中为可选依赖。未传入时，ReActLoop 行为与改动前完全一致，不触发任何 Hook。

#### Scenario: 未注入 HookManager
- **WHEN** ReActLoop 构造时未传入 hook_manager
- **THEN** _execute_action 中不触发任何 Hook 事件，工具正常执行
