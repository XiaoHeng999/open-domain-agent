## MODIFIED Requirements

### Requirement: 全局并发控制
SubagentManager SHALL 强制执行并发限制，防止资源耗尽。

#### Scenario: 并发上限检查
- **WHEN** 创建新子代理且活跃子代理数 >= config.max_concurrent
- **THEN** SHALL 等待直到活跃子代理数降至 max_concurrent 以下
- **THEN** 等待超时后 SHALL 返回错误 "Subagent concurrency limit reached"

#### Scenario: 每父代理子代理数量限制 SHALL 被执行
- **WHEN** 同一父代理（parent_id）的活跃子代理数 >= config.max_children
- **THEN** SHALL 拒绝创建新子代理，返回错误 `"Per-parent subagent limit (max_children={max_children}) reached for parent {parent_id}"`
- **THEN** SubagentTool 的 execute() SHALL 返回该错误消息

#### Scenario: 子代理完成后释放父代理配额
- **WHEN** parent_id="agent-1" 之前创建了 max_children=3 个子代理，其中一个完成执行
- **THEN** SHALL 从 children_by_parent["agent-1"] 中移除已完成的子代理
- **THEN** parent_id="agent-1" 可以再创建一个新的子代理

#### Scenario: stop_all 清理所有父代理配额
- **WHEN** SubagentManager.stop_all() 被调用
- **THEN** SHALL 清空 children_by_parent 字典中所有父代理的子代理集合
