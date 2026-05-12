## 1. UnifiedLLMRouter 接收 history 参数

- [x] 1.1 `src/open_agent/routing/unified.py`: `route()` 方法增加可选参数 `history: list[dict[str, str]] | None = None`，当 history 非空时将其插入到 system prompt 和当前 user_input 之间的 messages 列表中
- [x] 1.2 验证：history 为 None 或空列表时，messages 结构与改动前一致（仅 `[system, user_input]`）

## 2. RoutingPipeline 透传 history

- [x] 2.1 `src/open_agent/routing/router.py`: `route()` 方法增加可选参数 `history: list[dict[str, str]] | None = None`
- [x] 2.2 `src/open_agent/routing/router.py`: `_route_unified()` 方法增加 history 参数，透传给 `self._unified_router.route(user_input, history=history)`
- [x] 2.3 `src/open_agent/routing/router.py`: `_route_keyword()` 不接收 history，保持不变（keyword 管线无上下文需求）

## 3. AgentRuntime 注入 history 到 routing

- [x] 3.1 `src/open_agent/runtime.py`: 在 `run()` 方法的 routing 调用前，从 `self._runtime_memory` 获取最近 4 条消息作为 routing history
- [x] 3.2 `src/open_agent/runtime.py`: 将 history 传入 `self.routing_pipeline.route(user_input, history=history, trace=trace)`

## 4. 测试

- [x] 4.1 为 `UnifiedLLMRouter.route()` 编写单元测试：验证有 history 时 LLM messages 包含历史消息、无 history 时向后兼容
- [x] 4.2 为 `RoutingPipeline.route()` 编写单元测试：验证 history 透传到 unified 路径、keyword fallback 不使用 history
- [x] 4.3 编写多轮对话集成测试：第一轮 "2+2等于几？" → 第二轮 "再加100等于几？" → 验证不触发 missing_slots 澄清，正常进入 ReAct loop
