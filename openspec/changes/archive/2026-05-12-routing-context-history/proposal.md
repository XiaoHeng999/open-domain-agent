## Why

Routing 层（UnifiedLLMRouter）完全无状态——每次只看当前 user_input，看不到对话历史。这导致多轮对话中的指代消解（"再加100" → 上一轮的 "4"）在 routing 阶段就失败：LLM 判定 `missing_slots=["base_number"]`，runtime 直接返回澄清问题，ReAct loop 根本没机会用历史上下文来理解用户意图。问题本质是**无状态 Intent 与有状态 Runtime 之间的 gap**。

## What Changes

- UnifiedLLMRouter.route() 接收可选的 `history` 参数（最近 2-3 轮对话），拼入 LLM messages，使 routing LLM 能看到上下文
- RoutingPipeline.route() 从 RuntimeMemory 获取精简历史（最近 4 条消息），传入 UnifiedLLMRouter
- AgentRuntime.run() 在调用 routing_pipeline.route() 时传入 runtime_memory 的历史上下文
- missing_slots 判定逻辑不变——只是 LLM 现在能看到历史，会自动从上下文中推断出槽位值，而非误判为缺失

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `unified-llm-router`: route() 方法增加 history 参数，LLM messages 中注入对话历史，使路由决策具备上下文感知能力
- `routing-runtime-integration`: RoutingPipeline 从 RuntimeMemory 获取精简历史并传递给 router；missing_slots 澄清场景增加多轮上下文判断
- `intent-recognition`: Intent Parser 需求更新——在有对话历史时，LLM 应能从上下文中推断槽位值，而非仅依赖当前输入

## Impact

- **代码改动**：`src/open_agent/routing/unified.py`（messages 构建）、`src/open_agent/routing/router.py`（history 传递）、`src/open_agent/runtime.py`（runtime_memory → routing 调用链路）
- **Token 成本**：routing LLM 每轮增加约 200-500 tokens（最近 2-3 轮历史），可通过截断策略控制
- **延迟**：小模型 +200-500 tokens 增加约 50-100ms，可接受
- **向后兼容**：history 参数可选，缺省时行为与改动前一致
- **无 BREAKING 变更**：所有改动均为新增可选参数，不影响现有调用方式
