## 1. Runtime 层：missing_slots 处理路径改造

- [x] 1.1 修改 `runtime.py:360-372`：将 `if routing_decision.intent.missing_slots` 条件改为 `if routing_decision.intent.missing_slots and routing_decision.complexity.complexity == "simple"`，仅简单任务触发短路
- [x] 1.2 在 `runtime.py` 中增加 missing_slots 上下文注入逻辑：当 `missing_slots` 非空且 complexity 非 simple 时，构造一条 system hint 消息注入 Agent 消息列表，提示缺失参数但建议可推断时直接执行
- [x] 1.3 验证注入的 hint 消息出现在 Agent 系统提示的正确位置（在 core identity 之后、用户消息之前）

## 2. 路由器 Prompt：增加可推断性判断规则

- [x] 2.1 修改 `src/open_agent/routing/unified.py` 的 `_SYSTEM_PROMPT_TEMPLATE`：在规则部分增加可推断性判断指导——仅当参数完全无法推断且任务无法执行时才标记 missing_slots；如果参数可通过工具自动决定（如文件名、编程语言）则视为可推断
- [x] 2.2 在 few-shot 示例中增加一个正例：用户未指定文件名但 missing_slots 为空的 case，强化 LLM 的可推断性判断

## 3. 路由调用：强制 temperature=0.0

- [x] 3.1 检查 `UnifiedLLMRouter.route()` 中 LLM 调用点，确保传入 `temperature=0.0` 参数 override
- [x] 3.2 验证当路由复用主 provider（未配置 routing_provider）时，temperature override 生效

## 4. 测试验证

- [x] 4.1 编写单元测试：验证 simple + missing_slots 触发短路返回澄清
- [x] 4.2 编写单元测试：验证 medium/complex + missing_slots 注入上下文而非短路
- [x] 4.3 编写单元测试：验证路由 prompt 可推断性规则对"创建代码未指定文件名"返回 missing_slots=[]
- [x] 4.4 集成测试：使用原始问题 prompt "帮我创建一个等差数列求和公式的代码" 验证 Agent 能正确使用 task 工具委派
- [x] 4.5 验证 temperature=0.0：相同输入连续调用 3 次，路由结果一致
