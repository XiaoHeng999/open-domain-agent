## 1. Bug 修复

- [x] 1.1 修复 `intent.py:50` 中 "review" 关键词重复的 bug
- [x] 1.2 修复 `runtime.py` 中 `RoutingConfig.domains` 未传递到 `RoutingPipeline` 和 `DomainRouter` 的 bug

## 2. 配置层扩展

- [x] 2.1 在 `RoutingConfig` 中新增 `routing_provider`、`routing_name`、`routing_api_key`、`routing_base_url` 可选字段
- [x] 2.2 在 `AgentRuntime.__init__` 中根据 routing config 创建独立的 routing provider 实例（不指定时复用主 provider）

## 3. UnifiedLLMRouter 实现

- [x] 3.1 新建 `routing/unified.py`，实现 `UnifiedLLMRouter` 类，包含 system prompt 模板（角色定义 + domains 描述 + intent 列表 + 复杂度规则 + JSON schema + few-shot 示例）
- [x] 3.2 实现 `UnifiedLLMRouter.route()` 方法：构建 prompt、调用 provider.complete_structured、解析 JSON 返回 `RoutingDecision`
- [x] 3.3 实现 JSON 解析失败的 fallback 逻辑：异常时 fallback 到 keyword 三阶段管线
- [x] 3.4 更新 `routing/__init__.py` 导出 `UnifiedLLMRouter`

## 4. RoutingPipeline 集成

- [x] 4.1 修改 `RoutingPipeline.__init__`：新增 `routing_provider` 参数，有 provider 时创建 `UnifiedLLMRouter`
- [x] 4.2 修改 `RoutingPipeline.route()`：有 UnifiedLLMRouter 时走统一路由，无时走 keyword 管线
- [x] 4.3 统一路由结果映射到 `RoutingDecision`（complexity 新增 medium 档位）
- [x] 4.4 在 routing trace 中记录 method（"llm" / "rule_fallback" / "rule"）

## 5. Runtime 路由结果接入

- [x] 5.1 将 `routing_decision.domain.system_prompt` 传入 `PromptBuilder`，注入 ReAct loop 的 system prompt
- [x] 5.2 实现 `skip_planning` 控制：skip_planning=False 时调用 `plan_generator.generate()`，将 Plan 注入 ReAct context
- [x] 5.3 实现 missing_slots 澄清流程：missing_slots 非空时直接返回澄清问题，不进入 ReAct loop

## 6. 测试

- [x] 6.1 新增 `tests/test_unified_routing.py`：测试 UnifiedLLMRouter 的 prompt 构建、JSON 解析、fallback 逻辑
- [x] 6.2 新增测试：routing config 独立模型配置（mock provider）
- [x] 6.3 新增测试：runtime 中 domain system_prompt 注入
- [x] 6.4 新增测试：runtime 中 skip_planning 控制 PlanGenerator 调用
- [x] 6.5 新增测试：runtime 中 missing_slots 澄清流程
- [x] 6.6 更新现有 `test_routing.py`：complexity 新增 medium 档位的测试用例
- [x] 6.7 运行全量测试确保无回归
