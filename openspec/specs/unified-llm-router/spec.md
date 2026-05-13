## ADDED Requirements

### Requirement: 单次 LLM 统一路由
系统 SHALL 提供 `UnifiedLLMRouter`，通过单次轻量 LLM 调用同时输出 complexity、domain、intent、slots、missing_slots、confidence，替代三阶段独立 keyword 匹配。`route()` 方法 SHALL 接受可选的 `history` 参数（`list[dict[str, str]]`），当 history 非空时将其注入到 LLM messages 中（位于 system prompt 和当前 user_input 之间），使路由决策具备上下文感知能力。当 history 为空或 None 时，行为 SHALL 与不传 history 完全一致。

#### Scenario: 中文语义路由
- **WHEN** 用户输入 "帮我看看这段代码哪有毛病" 且有 provider 可用
- **THEN** UnifiedLLMRouter 返回 domain="coding"、intent="debug_code"、complexity="simple"，不依赖 keyword 子串匹配

#### Scenario: 英文多意图路由
- **WHEN** 用户输入 "Research competing frameworks and write a comparison report"
- **THEN** UnifiedLLMRouter 返回 complexity="complex"、domain="search"、intent="research_compare"、slots 包含 output="report"

#### Scenario: 新 domain 自动支持
- **WHEN** 开发者通过 `register_domain("finance", ...)` 注册了 finance domain 且 domain 描述包含 "stock, investment, portfolio"
- **THEN** UnifiedLLMRouter 的 system prompt 自动包含 finance domain 描述，对 "分析股票投资组合" 返回 domain="finance"

#### Scenario: 有对话历史时从上下文推断槽位
- **WHEN** history 包含 `[{"role":"user","content":"2+2等于几？"}, {"role":"assistant","content":"2+2=4"}]` 且当前 user_input 为 "再加100等于几？"
- **THEN** UnifiedLLMRouter 返回 slots 包含 base_number=4（或等效值）、missing_slots=[]，而非判定 base_number 缺失

#### Scenario: 历史不足以推断时仍报 missing_slots
- **WHEN** history 为空且用户输入 "帮我搜索数据"
- **THEN** UnifiedLLMRouter 返回 missing_slots=["data_source","time_range"]，行为与无 history 时一致

#### Scenario: history 为 None 时向后兼容
- **WHEN** 调用 `route(user_input)` 不传 history 参数
- **THEN** LLM messages 仅包含 `[system, user_input]`，与改动前行为完全一致

### Requirement: LLM 路由 prompt 模板
系统 SHALL 使用包含以下结构的 system prompt：(1) 角色定义、(2) 可用 domains 及描述、(3) 各 domain 典型 intent 列表、(4) 复杂度分级规则、(5) 输出 JSON schema、(6) 中英文 few-shot 示例、**(7) 可推断性判断规则**。domains 描述 SHALL 从 `DomainRouter._domains` 动态读取。可推断性规则 SHALL 指导 LLM：仅当参数完全无法推断且任务无法执行时才标记 missing_slots；如果参数可通过工具自动决定（如文件名、编程语言）或可从任务语义合理推断，则不放入 missing_slots。

#### Scenario: 动态 domain 描述注入
- **WHEN** DomainRouter 包含 4 个 domains（coding, search, web, general）和 1 个自定义 domain（finance）
- **THEN** UnifiedLLMRouter 的 system prompt 列出全部 5 个 domains 及其描述

#### Scenario: 可推断参数不标记为 missing
- **WHEN** 用户输入 "帮我创建一个等差数列求和公式的代码"（未指定文件名和语言）
- **THEN** UnifiedLLMRouter 返回 `missing_slots=[]`，因为文件名和语言可由 Agent 通过工具合理推断

#### Scenario: 不可推断参数仍标记为 missing
- **WHEN** 用户输入 "帮我搜索数据"（未指定搜索目标和时间范围）
- **THEN** UnifiedLLMRouter 返回 `missing_slots=["data_source", "time_range"]`，因为这些参数无法从任务语义推断

### Requirement: 复杂度三档分类
系统 SHALL 将复杂度从 binary（simple/complex）扩展为三档：simple / medium / complex。

#### Scenario: medium 复杂度
- **WHEN** 用户输入 "帮我写一个 Python 排序函数"
- **THEN** complexity 返回 "medium"（单步任务但需要代码生成）

#### Scenario: simple 复杂度
- **WHEN** 用户输入 "你好" 或 "什么是 Python？"
- **THEN** complexity 返回 "simple"

#### Scenario: complex 复杂度
- **WHEN** 用户输入 "调研三个竞品并生成对比报告"
- **THEN** complexity 返回 "complex"

### Requirement: 路由 fallback 链
系统 SHALL 实现 fallback 链：有 provider 时走 UnifiedLLMRouter → LLM 调用失败时 fallback 到 keyword 三阶段管线 → 无 provider 时直接走 keyword 管线。fallback 事件 SHALL 记录在 trace 中。

#### Scenario: LLM 调用成功
- **WHEN** provider 可用且 LLM 返回有效 JSON
- **THEN** 使用 LLM 路由结果，trace 中 method="llm"

#### Scenario: LLM 调用失败 fallback
- **WHEN** provider 可用但 LLM 调用超时或返回无效 JSON
- **THEN** fallback 到 keyword 管线，trace 中 method="rule_fallback"，reason 记录失败原因

#### Scenario: 无 provider
- **WHEN** 未配置任何 provider
- **THEN** 直接走 keyword 管线，trace 中 method="rule"

### Requirement: 独立路由模型配置
系统 SHALL 支持在 `RoutingConfig` 中配置独立的路由模型（provider、name、api_key、base_url），不指定时复用主模型配置。

#### Scenario: 独立路由模型
- **WHEN** 配置 routing.routing_provider="openai"、routing.routing_name="gpt-4o-mini"
- **THEN** UnifiedLLMRouter 使用 gpt-4o-mini 进行路由，主 ReAct 循环仍使用 gpt-4o

#### Scenario: 复用主模型
- **WHEN** 未配置 routing_provider
- **THEN** UnifiedLLMRouter 复用主模型配置进行路由

### Requirement: 路由结果 JSON schema
UnifiedLLMRouter 的 LLM 输出 SHALL 遵循以下 JSON schema：

```json
{
  "complexity": "simple" | "medium" | "complex",
  "confidence": 0.0-1.0,
  "domain": "<domain_name>",
  "domain_candidates": ["<domain1>", ...],
  "intent": "<intent_name>",
  "slots": {},
  "missing_slots": [],
  "reason": "<brief explanation>"
}
```

#### Scenario: 完整路由输出
- **WHEN** 用户输入 "搜索2024年的财报数据"
- **THEN** 返回 JSON 包含 complexity、confidence、domain="search"、intent="search_report"、slots={"year":"2024","type":"财报"}、missing_slots=[]

### Requirement: 路由调用温度强制为零
UnifiedLLMRouter 的 `route()` 方法 SHALL 在调用 LLM 时显式传入 `temperature=0.0`，无论 provider 的默认 temperature 设置如何。这确保相同输入产生相同的路由结果。

#### Scenario: 复用主 provider 时 temperature 仍为零
- **WHEN** 未配置 routing_provider，UnifiedLLMRouter 复用主 provider（temperature=0.7）
- **THEN** `route()` 调用 LLM 时传入 temperature=0.0 override，路由结果稳定可复现

#### Scenario: 独立路由模型配置时行为不变
- **WHEN** 配置了 routing_provider 和 routing_name
- **THEN** `route()` 调用 LLM 时仍传入 temperature=0.0，与独立配置中的 temperature=0.0 一致
