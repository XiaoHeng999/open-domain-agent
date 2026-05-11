## MODIFIED Requirements

### Requirement: Domain Agent 上下文隔离
系统 SHALL 使用同一个 Agent 类但不同 system prompt 实现不同 domain agent（coding / search / web / general），保证各 domain 的上下文互不污染。每个逻辑 agent SHALL 可以拥有独立的工具子集，通过 PromptPipeline 的 ToolListSegment 动态注入。Domain system prompt SHALL 从路由结果中获取并注入 ReAct loop 的 system prompt。

#### Scenario: Domain 切换上下文隔离（现有行为保持）
- **WHEN** 用户先在 coding domain 执行任务，然后切换到 search domain
- **THEN** search domain 的 context 不包含 coding domain 的中间状态，仅共享 episodic memory 和 user profile

#### Scenario: Domain system prompt 注入（新增行为）
- **WHEN** 路由结果 domain="coding"，system_prompt="You are an expert coding assistant..."
- **THEN** ReAct loop 的 system prompt 使用路由返回的 domain system_prompt，而非硬编码默认 prompt

#### Scenario: 逻辑 agent 工具集隔离（现有行为保持）
- **WHEN** coding domain agent 激活时，其 ToolListSegment 只渲染 tags 包含 "coding" 的工具
- **THEN** LLM 只能看到 coding 相关工具（如 file_read, file_write, search），不会尝试调用 web_browse 等无关工具

#### Scenario: 新 domain 注册
- **WHEN** 开发者注册一个新 domain "data_analysis" 并提供对应的 system prompt 和工具 tag 过滤条件
- **THEN** Domain Router 可以路由到该 domain，Agent 使用对应的 system prompt 和工具子集

### Requirement: 简单任务直通模式
系统 SHALL 支持简单任务跳过 planning step，直接进入 ReAct 循环。直通模式下 SHALL 使用默认全量工具集而非过滤后的子集。Planning 控制 SHALL 在 runtime 中实际生效：skip_planning=False 时调用 PlanGenerator。

#### Scenario: 简单任务快速路径（现有行为保持）
- **WHEN** Complexity Judge 判定为 simple 且 confidence > 0.9
- **THEN** 跳过 planning step，直接进入 ReAct 循环，使用全量工具集

#### Scenario: 复杂任务触发规划（新增行为）
- **WHEN** routing_decision.skip_planning == False
- **THEN** AgentRuntime 调用 plan_generator.generate()，生成计划注入 ReAct context
