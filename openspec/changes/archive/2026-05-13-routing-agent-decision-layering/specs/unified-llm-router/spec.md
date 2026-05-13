## MODIFIED Requirements

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

### Requirement: 路由调用温度强制为零
UnifiedLLMRouter 的 `route()` 方法 SHALL 在调用 LLM 时显式传入 `temperature=0.0`，无论 provider 的默认 temperature 设置如何。这确保相同输入产生相同的路由结果。

#### Scenario: 复用主 provider 时 temperature 仍为零
- **WHEN** 未配置 routing_provider，UnifiedLLMRouter 复用主 provider（temperature=0.7）
- **THEN** `route()` 调用 LLM 时传入 temperature=0.0 override，路由结果稳定可复现

#### Scenario: 独立路由模型配置时行为不变
- **WHEN** 配置了 routing_provider 和 routing_name
- **THEN** `route()` 调用 LLM 时仍传入 temperature=0.0，与独立配置中的 temperature=0.0 一致
