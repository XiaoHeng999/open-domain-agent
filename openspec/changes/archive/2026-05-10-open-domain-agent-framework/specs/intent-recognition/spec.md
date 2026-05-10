## ADDED Requirements

### Requirement: 三阶段路由管线
系统 SHALL 提供三阶段路由：Complexity Judge（判断简单/复杂）→ Domain Router（路由到 domain agent）→ Intent Parser（提取结构化 intent + slots）。前两阶段可使用 rule-based 或轻量 LLM（如 DeepSeek）。

#### Scenario: 简单任务快速路径
- **WHEN** 用户输入 "今天天气怎么样"
- **THEN** Complexity Judge 判定为 simple（confidence > 0.9），跳过 planning step，直接进入 ReAct 循环

#### Scenario: 复杂任务触发规划
- **WHEN** 用户输入 "调研三个竞品并生成对比报告"
- **THEN** Complexity Judge 判定为 complex，Domain Router 路由到 search domain，Intent Parser 提取 intent=research_compare、slots={targets: 3, output: report}

#### Scenario: 路由到不同 domain agent
- **WHEN** 用户输入 "帮我写一个排序函数"
- **THEN** Domain Router 路由到 coding domain（同一个 Agent 类，不同 system prompt），上下文与其他 domain 隔离

### Requirement: Complexity Judge
系统 SHALL 实现任务复杂度判断，输出 complexity (simple/complex) + confidence，支持 rule-based 和轻量 LLM 两种实现。

#### Scenario: Rule-based 快速判断
- **WHEN** 用户输入短于 20 字且不包含多步骤关键词（如 "并且"、"然后"、"对比"）
- **THEN** Complexity Judge 直接返回 simple，不调用 LLM，latency < 10ms

#### Scenario: LLM 辅助判断
- **WHEN** rule-based 判断 confidence < 0.7
- **THEN** 调用轻量 LLM（DeepSeek）进行复杂度判断，返回 complexity + confidence + reason

### Requirement: Domain Router
系统 SHALL 将请求路由到对应 domain（coding / search / web / general 等），每个 domain 使用独立的 system prompt，保证上下文隔离。

#### Scenario: Domain 分类
- **WHEN** 用户输入包含编程相关关键词或上下文
- **THEN** Domain Router 路由到 coding domain，使用 coding system prompt

#### Scenario: 未匹配 domain 降级
- **WHEN** 请求无法匹配任何专门 domain
- **THEN** 路由到 general domain，并在 trace 中标记 routed_as_fallback=true

### Requirement: Intent Parser
系统 SHALL 在 domain 内提取结构化 intent 和 slots，支持必需参数缺失时生成澄清问题。

#### Scenario: 完整 intent 提取
- **WHEN** 用户输入 "搜索2024年的财报数据"
- **THEN** Intent Parser 提取 intent="search_report"、slots={year: "2024", type: "财报"}

#### Scenario: 槽位缺失触发澄清
- **WHEN** intent 已识别但必需槽位缺失
- **THEN** 系统生成针对性的澄清问题，仅询问缺失的槽位

### Requirement: 路由可观测性
系统 SHALL 为每次路由决策生成 trace，包含三阶段的完整结果。

#### Scenario: 路由 trace
- **WHEN** 一次路由完成
- **THEN** trace 包含 complexity_judge（complexity + confidence + method）、domain_router（domain + candidates）、intent_parser（intent + slots）

### Requirement: 意图识别评测接口
系统 SHALL 暴露路由模块的独立评测接口，接受测试集并输出各阶段 accuracy。

#### Scenario: 评测执行
- **WHEN** 提交 100 条测试样本
- **THEN** 返回 complexity_accuracy、domain_accuracy、intent_accuracy、slot_f1、avg_latency_ms
