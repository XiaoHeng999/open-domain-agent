## ADDED Requirements

### Requirement: Complexity Judge 集成到路由层
系统 SHALL 将 Complexity Judge 作为路由层的第一阶段，输出 complexity (simple/complex) + confidence。支持 rule-based 和轻量 LLM 两种实现方式。

#### Scenario: Rule-based 复杂度判断
- **WHEN** 用户输入为短问题且无多步骤关键词
- **THEN** Complexity Judge 返回 {complexity: "simple", confidence: 0.95, method: "rule"}，不调用 LLM

#### Scenario: LLM 辅助复杂度判断
- **WHEN** rule-based 无法高置信度判断
- **THEN** 调用轻量 LLM 返回 {complexity: "complex", confidence: 0.85, method: "llm", reason: "多步骤任务"}

### Requirement: Domain Agent 上下文隔离
系统 SHALL 使用同一个 Agent 类但不同 system prompt 实现不同 domain agent（coding / search / web / general），保证各 domain 的上下文互不污染。

#### Scenario: Domain 切换上下文隔离
- **WHEN** 用户先在 coding domain 执行任务，然后切换到 search domain
- **THEN** search domain 的 context 不包含 coding domain 的中间状态，仅共享 episodic memory 和 user profile

#### Scenario: 新 domain 注册
- **WHEN** 开发者注册一个新 domain "data_analysis" 并提供对应的 system prompt
- **THEN** Domain Router 可以路由到该 domain，Agent 使用对应的 system prompt

### Requirement: 路由决策可解释性
系统 SHALL 为每次路由决策生成可解释的 trace，包含三阶段的完整决策过程。

#### Scenario: 路由 trace 完整性
- **WHEN** 一次完整路由完成
- **THEN** trace 包含 complexity_judge 结果、domain_router 候选列表和选择理由、intent_parser 提取结果

### Requirement: 简单任务直通模式
系统 SHALL 支持简单任务跳过 planning step，直接进入 ReAct 循环。

#### Scenario: 简单任务快速路径
- **WHEN** Complexity Judge 判定为 simple 且 confidence > 0.9
- **THEN** 跳过 planning step，直接进入 ReAct 循环，减少延迟
