## MODIFIED Requirements

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
