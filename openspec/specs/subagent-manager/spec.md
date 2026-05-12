## ADDED Requirements

### Requirement: SubagentManager 生命周期管理
SubagentManager SHALL 管理子代理的完整生命周期：预设注册、实例创建、并发控制、结果存储、级联终止。

#### Scenario: SubagentManager 初始化
- **WHEN** AgentRuntime 创建 SubagentManager（传入 provider、tool_registry、config）
- **THEN** SHALL 加载配置中的预设类型到内部 registry
- **THEN** SHALL 初始化活跃子代理跟踪列表为空

#### Scenario: 创建子代理实例
- **WHEN** SubagentTool 调用 manager.create_subagent(subagent_type, prompt, max_turns)
- **THEN** SHALL 从预设 registry 查找 subagent_type 对应的配置
- **THEN** SHALL 创建受限 ToolRegistry（仅包含预设允许的工具名）
- **THEN** SHALL 创建新的 ReActLoop 实例（受限 registry + 预设系统提示 + max_iterations=max_turns）
- **THEN** SHALL 返回子代理实例及其 agent_id

#### Scenario: 预设类型不存在
- **WHEN** 请求的 subagent_type 在预设 registry 中不存在
- **THEN** SHALL 回退到 "general" 预设类型
- **THEN** SHALL 在日志中记录 warning

### Requirement: 全局并发控制
SubagentManager SHALL 强制执行并发限制，防止资源耗尽。

#### Scenario: 并发上限检查
- **WHEN** 创建新子代理且活跃子代理数 >= config.max_concurrent
- **THEN** SHALL 等待直到活跃子代理数降至 max_concurrent 以下
- **THEN** 等待超时后 SHALL 返回错误 "Subagent concurrency limit reached"

#### Scenario: 每父代理子代理数量限制
- **WHEN** 同一父代理的活跃子代理数 >= config.max_children
- **THEN** SHALL 拒绝创建新子代理，返回错误 "Per-parent subagent limit reached"

### Requirement: 后台任务结果存储
SubagentManager SHALL 存储后台子代理的执行结果，支持后续查询。

#### Scenario: 后台结果存储
- **WHEN** 后台子代理完成执行
- **THEN** 结果 SHALL 以 agent_id 为键存储在 manager 的结果字典中
- **THEN** 结果 SHALL 包含：answer（string）、success（bool）、duration_ms（float）

#### Scenario: 查询后台结果
- **WHEN** 调用 manager.get_result(agent_id)
- **THEN** 如果子代理已完成，返回结果字典
- **THEN** 如果子代理仍在运行，返回 {"status": "running"}
- **THEN** 如果 agent_id 不存在，返回 {"status": "not_found"}

### Requirement: 级联终止
当父代理停止时，SubagentManager SHALL 终止所有活跃子代理。

#### Scenario: 级联停止
- **WHEN** AgentRuntime.on_stop() 调用 SubagentManager.stop_all()
- **THEN** SHALL 对每个活跃子代理的 asyncio.Task 调用 cancel()
- **THEN** SHALL 等待所有任务完成取消（带超时）
- **THEN** SHALL 清空活跃子代理列表

#### Scenario: 单个子代理超时
- **WHEN** 子代理执行时间超过其 max_turns * 估算单步时长
- **THEN** SubagentManager SHALL 强制终止该子代理
- **THEN** SHALL 在结果中标记 success=false，内容为 "Subagent timed out"

### Requirement: SubagentManager 与 Runtime 集成
AgentRuntime SHALL 在 on_start 中初始化 SubagentManager 并注册 SubagentTool。

#### Scenario: Runtime 自动注册
- **WHEN** AgentRuntime.on_start() 执行
- **THEN** SHALL 创建 SubagentManager 实例（传入 provider、tool_registry、config.subagent）
- **THEN** SHALL 创建 SubagentTool（注入 manager 引用）
- **THEN** SHALL 将 SubagentTool 注册到 ToolRegistry
- **THEN** 当 config.subagent.enabled=false 时 SHALL 跳过注册

#### Scenario: Runtime 级联停止
- **WHEN** AgentRuntime.on_stop() 执行
- **THEN** SHALL 调用 SubagentManager.stop_all() 终止所有活跃子代理
