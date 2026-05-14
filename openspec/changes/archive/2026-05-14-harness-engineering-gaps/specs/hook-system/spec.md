## MODIFIED Requirements

### Requirement: HookResult 数据结构
系统 SHALL 定义 `HookResult` 数据结构，包含 `content`（可选字符串，注入到 message 流）、`blocked`（布尔值，为 True 时阻止工具执行或拒绝工具结果）、`metadata`（字典，存储审计等非注入数据）。`blocked` 字段在 `TOOL_BEFORE` 事件中阻止工具执行，在 `TOOL_AFTER` 事件中拒绝工具结果并触发 recovery。

#### Scenario: HookResult 默认值
- **WHEN** 创建 HookResult 未指定参数
- **THEN** content 为 None、blocked 为 False、metadata 为空字典

#### Scenario: TOOL_BEFORE blocked=True 阻止工具执行
- **WHEN** TOOL_BEFORE Hook 返回 HookResult(blocked=True, content="Blocked: requires confirmation")
- **THEN** 工具不执行，Observation 的 content 为 "Blocked: requires confirmation"，success 为 False

#### Scenario: TOOL_AFTER blocked=True 拒绝工具结果
- **WHEN** TOOL_AFTER Hook 返回 HookResult(blocked=True, content="Blocked: output quality check failed")
- **THEN** 工具结果被拒绝，Observation 的 content 为 "Blocked: output quality check failed"，success 为 False
- **THEN** ReAct 循环 SHALL 调用 _try_recover() 尝试恢复

### Requirement: HookManager 注册与触发
系统 SHALL 提供 `HookManager` 类，支持通过 `register(event, callback, priority)` 注册 Hook 回调，通过 `fire(event, context)` 触发指定事件的所有回调。回调按 priority 升序执行（数值越小越先执行），同优先级按注册顺序。TOOL_BEFORE 和 TOOL_AFTER 事件中，任一 Hook 返回 `blocked=True` SHALL 中断后续 Hook 执行。

#### Scenario: 按优先级顺序执行
- **WHEN** 注册 priority=10 的 Hook A 和 priority=5 的 Hook B 到 TOOL_BEFORE
- **THEN** fire(TOOL_BEFORE, {}) 先执行 B 再执行 A

#### Scenario: TOOL_BEFORE 链中 blocked 中断
- **WHEN** TOOL_BEFORE 有两个 Hook，第一个返回 blocked=True
- **THEN** 第二个 Hook 不执行，工具不执行

#### Scenario: TOOL_AFTER 链中 blocked 中断
- **WHEN** TOOL_AFTER 有两个 Hook，第一个返回 blocked=True
- **THEN** 第二个 Hook 不执行，工具结果被拒绝

#### Scenario: fire 返回所有结果
- **WHEN** 三个 Hook 都返回 HookResult（无 blocked）
- **THEN** fire 返回包含三个 HookResult 的列表
