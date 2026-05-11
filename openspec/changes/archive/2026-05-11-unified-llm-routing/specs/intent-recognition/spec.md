## MODIFIED Requirements

### Requirement: 三阶段路由管线
系统 SHALL 提供三阶段路由：Complexity Judge（判断 simple/medium/complex）→ Domain Router（路由到 domain agent）→ Intent Parser（提取结构化 intent + slots）。主路径 SHALL 使用 UnifiedLLMRouter 单次 LLM 调用；无 provider 或 LLM 失败时 SHALL fallback 到 rule-based 三阶段管线。

#### Scenario: 简单任务快速路径
- **WHEN** 用户输入 "今天天气怎么样"
- **THEN** 路由判定为 simple（confidence > 0.9），跳过 planning step，直接进入 ReAct 循环

#### Scenario: 复杂任务触发规划
- **WHEN** 用户输入 "调研三个竞品并生成对比报告"
- **THEN** 路由判定为 complex，domain 路由到 search，intent 提取 intent=research_compare、slots={targets: 3, output: report}，触发 PlanGenerator

#### Scenario: 路由到不同 domain agent
- **WHEN** 用户输入 "帮我写一个排序函数"
- **THEN** 路由到 coding domain，使用 coding system prompt，上下文与其他 domain 隔离

#### Scenario: LLM 路由失败 fallback
- **WHEN** UnifiedLLMRouter LLM 调用超时
- **THEN** fallback 到 keyword 三阶段管线，trace 中记录 method="rule_fallback"

### Requirement: Complexity Judge
系统 SHALL 实现任务复杂度判断，输出 complexity (simple/medium/complex) + confidence，支持 rule-based 和 LLM 两种实现。

#### Scenario: Rule-based 快速判断
- **WHEN** 用户输入短于 50 字且不包含多步骤关键词
- **THEN** Complexity Judge 直接返回 simple，不调用 LLM，latency < 10ms

#### Scenario: LLM 辅助判断
- **WHEN** rule-based 判断 confidence < 0.7
- **THEN** 调用 UnifiedLLMRouter 进行路由，返回 complexity（含 medium 档位）+ confidence + reason

### Requirement: Intent Parser
系统 SHALL 在 domain 内提取结构化 intent 和 slots，支持必需参数缺失时生成澄清问题。澄清问题 SHALL 在 runtime 中实际触发，阻断 ReAct loop 执行。

#### Scenario: 完整 intent 提取
- **WHEN** 用户输入 "搜索2024年的财报数据"
- **THEN** Intent Parser 提取 intent="search_report"、slots={year: "2024", type: "财报"}、missing_slots=[]

#### Scenario: 槽位缺失触发澄清（runtime 接入）
- **WHEN** intent 已识别但 missing_slots 非空
- **THEN** runtime 直接返回澄清问题给用户，不进入 ReAct loop
