## MODIFIED Requirements

### Requirement: Domain Agent 上下文隔离
系统 SHALL 使用同一个 Agent 类但不同 system prompt 实现不同 domain agent（coding / search / web / general），保证各 domain 的上下文互不污染。每个逻辑 agent SHALL 可以拥有独立的工具子集，通过 PromptPipeline 的 ToolListSegment 动态注入。

#### Scenario: Domain 切换上下文隔离（现有行为保持）
- **WHEN** 用户先在 coding domain 执行任务，然后切换到 search domain
- **THEN** search domain 的 context 不包含 coding domain 的中间状态，仅共享 episodic memory 和 user profile

#### Scenario: 逻辑 agent 工具集隔离（新增）
- **WHEN** coding domain agent 激活时，其 ToolListSegment 只渲染 tags 包含 "coding" 的工具
- **THEN** LLM 只能看到 coding 相关工具（如 file_read, file_write, search），不会尝试调用 web_browse 等无关工具

#### Scenario: 新 domain 注册
- **WHEN** 开发者注册一个新 domain "data_analysis" 并提供对应的 system prompt 和工具 tag 过滤条件
- **THEN** Domain Router 可以路由到该 domain，Agent 使用对应的 system prompt 和工具子集

### Requirement: 简单任务直通模式
系统 SHALL 支持简单任务跳过 planning step，直接进入 ReAct 循环。直通模式下 SHALL 使用默认全量工具集而非过滤后的子集。

#### Scenario: 简单任务快速路径
- **WHEN** Complexity Judge 判定为 simple 且 confidence > 0.9
- **THEN** 跳过 planning step，直接进入 ReAct 循环，使用全量工具集

## ADDED Requirements

### Requirement: ToolRegistry 快照与恢复
系统 SHALL 为 ToolRegistry 提供 snapshot() 和 restore() 方法，支持工具集状态快照和恢复，用于逻辑 agent 分层切换。

#### Scenario: 工具集快照
- **WHEN** 调用 registry.snapshot()
- **THEN** 返回当前所有已注册工具名称的列表（frozenset）

#### Scenario: 快照恢复
- **WHEN** 调用 registry.restore(snapshot) 传入之前保存的快照
- **THEN** ToolRegistry 恢复到快照时的工具集状态

#### Scenario: 按标签过滤工具
- **WHEN** 调用 registry.filter_by_tags(["coding", "file"])
- **THEN** 返回仅包含具有 coding 或 file 标签的工具条目列表
