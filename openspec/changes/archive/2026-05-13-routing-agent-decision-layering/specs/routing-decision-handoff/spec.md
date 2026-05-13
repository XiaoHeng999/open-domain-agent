## ADDED Requirements

### Requirement: missing_slots 上下文注入
当路由层检测到 `missing_slots` 非空且任务复杂度为 `medium` 或 `complex` 时，runtime SHALL NOT 短路返回澄清问题，而是将 `missing_slots` 构造为一条上下文提示消息注入 Agent 的消息列表中，让 Agent 自主决定是追问用户还是用工具补全。

#### Scenario: 复杂任务信息不完整时注入提示
- **WHEN** 路由结果为 `complexity="complex"`、`missing_slots=["file_name", "language"]`
- **THEN** runtime 不返回澄清问题，而是将 missing_slots 信息作为 system hint 注入 Agent 上下文
- **THEN** Agent 进入 ReAct 循环，可自主使用 `task` 工具委派 sub-agent 完成任务

#### Scenario: 中等复杂任务信息不完整时注入提示
- **WHEN** 路由结果为 `complexity="medium"`、`missing_slots=["output_format"]`
- **THEN** runtime 不返回澄清问题，而是将 missing_slots 信息作为 system hint 注入 Agent 上下文
- **THEN** Agent 进入 ReAct 循环，可自行推断或追问

#### Scenario: 注入的提示消息格式
- **WHEN** missing_slots=["file_name", "language"] 被注入
- **THEN** Agent 上下文中包含一条提示，告知以下参数可能缺失，并建议在可推断时直接执行

### Requirement: complexity 分层门控
runtime SHALL 仅在 `complexity == "simple"` 且 `missing_slots` 非空时触发短路返回澄清问题。`medium` 和 `complex` 任务即使有 `missing_slots` 也 SHALL 放行到 Agent。

#### Scenario: 简单任务缺参数触发追问
- **WHEN** 路由结果为 `complexity="simple"`、`missing_slots=["city"]`、用户输入 "今天天气怎么样"
- **THEN** runtime 直接返回澄清问题，不进入 ReAct 循环

#### Scenario: 简单任务无缺失参数正常放行
- **WHEN** 路由结果为 `complexity="simple"`、`missing_slots=[]`
- **THEN** runtime 正常进入 ReAct 循环

#### Scenario: 复杂任务有缺失参数仍然放行
- **WHEN** 路由结果为 `complexity="complex"`、`missing_slots=["file_name"]`
- **THEN** runtime 不短路，注入 missing_slots 提示后进入 ReAct 循环
