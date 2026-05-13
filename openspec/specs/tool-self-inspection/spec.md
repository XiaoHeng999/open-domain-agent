## ADDED Requirements

### Requirement: Self 工具状态查询
`self` 工具 SHALL 提供 `action="status"` 操作，返回 Agent 当前运行时状态的 JSON 摘要，包括：当前迭代步骤数、已用工具列表、对话轮次、当前 max_iterations 设置、会话 ID。

#### Scenario: 查询运行时状态
- **WHEN** Agent 调用 `self` 工具并传入 `action="status"`
- **THEN** SHALL 返回包含 `step_count`、`tools_used`、`turn_count`、`max_iterations` 字段的 JSON 字符串

### Requirement: Self 工具配置查看
`self` 工具 SHALL 提供 `action="get_config"` 操作，返回指定配置参数的当前值。

#### Scenario: 查看单个配置参数
- **WHEN** Agent 调用 `self` 工具并传入 `action="get_config"` 和 `key="max_iterations"`
- **THEN** SHALL 返回该参数的当前值

### Requirement: Self 工具配置修改
`self` 工具 SHALL 提供 `action="set_config"` 操作，允许动态修改白名单内的运行时参数。白名单 SHALL 包括：`max_iterations`、`staleness_rounds`。

#### Scenario: 修改允许的配置参数
- **WHEN** Agent 调用 `self` 工具并传入 `action="set_config"`、`key="max_iterations"`、`value=20`
- **THEN** SHALL 将 ReActLoop 的 max_iterations 更新为 20
- **THEN** SHALL 返回确认消息

#### Scenario: 修改不在白名单的参数
- **WHEN** Agent 调用 `self` 工具并传入 `action="set_config"`、`key="provider"`
- **THEN** SHALL 返回错误信息，拒绝修改

### Requirement: Self 工具安全属性
`self` 工具 SHALL 标记为 `read_only=False`（因为 set_config 有副作用），`safety_checks` SHALL 包含 `"config"` 类型。

#### Scenario: 安全检查标记
- **WHEN** `self` 工具注册到 ToolRegistry
- **THEN** `read_only` SHALL 为 False
- **THEN** `safety_checks` SHALL 包含 `["config"]`
