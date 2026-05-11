## ADDED Requirements

### Requirement: 单次 LLM 统一路由
系统 SHALL 提供 `UnifiedLLMRouter`，通过单次轻量 LLM 调用同时输出 complexity、domain、intent、slots、missing_slots、confidence，替代三阶段独立 keyword 匹配。

#### Scenario: 中文语义路由
- **WHEN** 用户输入 "帮我看看这段代码哪有毛病" 且有 provider 可用
- **THEN** UnifiedLLMRouter 返回 domain="coding"、intent="debug_code"、complexity="simple"，不依赖 keyword 子串匹配

#### Scenario: 英文多意图路由
- **WHEN** 用户输入 "Research competing frameworks and write a comparison report"
- **THEN** UnifiedLLMRouter 返回 complexity="complex"、domain="search"、intent="research_compare"、slots 包含 output="report"

#### Scenario: 新 domain 自动支持
- **WHEN** 开发者通过 `register_domain("finance", ...)` 注册了 finance domain 且 domain 描述包含 "stock, investment, portfolio"
- **THEN** UnifiedLLMRouter 的 system prompt 自动包含 finance domain 描述，对 "分析股票投资组合" 返回 domain="finance"

### Requirement: LLM 路由 prompt 模板
系统 SHALL 使用包含以下结构的 system prompt：(1) 角色定义、(2) 可用 domains 及描述、(3) 各 domain 典型 intent 列表、(4) 复杂度分级规则、(5) 输出 JSON schema、(6) 中英文 few-shot 示例。domains 描述 SHALL 从 `DomainRouter._domains` 动态读取。

#### Scenario: 动态 domain 描述注入
- **WHEN** DomainRouter 包含 4 个 domains（coding, search, web, general）和 1 个自定义 domain（finance）
- **THEN** UnifiedLLMRouter 的 system prompt 列出全部 5 个 domains 及其描述

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
