## ADDED Requirements

### Requirement: Scenario Definition 数据模型
系统 SHALL 提供评测场景的标准数据模型，包含：输入、预期工具调用序列、预期输出、per-step assertions。

#### Scenario: 完整场景定义
- **WHEN** 定义一个场景：输入 "搜索财报" → 预期 tool_call search_tool(query="财报") → 预期输出包含财报摘要
- **THEN** 场景数据模型包含 input、expected_tool_calls（有序列表）、expected_output、step_assertions

#### Scenario: Per-Step Assertion 定义
- **WHEN** 场景中定义 "第 2 步应调用 search_tool 且参数包含 query"
- **THEN** assertion 格式为 {step: 2, type: "tool_called_with", tool: "search_tool", params_contain: {query: str}}

### Requirement: Trace Replay 引擎
系统 SHALL 支持重放执行 trace，逐 step 对比实际输出与预期，执行 assertion 检查。

#### Scenario: 逐 step 对比
- **WHEN** 提交一个包含 5 步的评测场景并执行
- **THEN** replay 引擎逐步对比：实际 tool call vs 预期 tool call、实际输出 vs 预期输出、每步 assertion pass/fail

#### Scenario: Assertion 类型支持
- **WHEN** 场景中包含多种 assertion 类型（tool_called_with、output_matches、state_equals、output_contains）
- **THEN** 每种 assertion 都有对应的检查逻辑，输出 pass/fail + 具体差异

### Requirement: 评测指标计算
系统 SHALL 计算并汇总：Intent Accuracy、Tool Call Success Rate、Task Completion Rate、Average Turns to Completion。

#### Scenario: 指标汇总
- **WHEN** 一组评测场景执行完成
- **THEN** 输出指标报告，每个指标包含 mean、p50、p95 和 per-scenario 明细

### Requirement: LLM-as-Judge（仅最终输出）
系统 SHALL 仅在最终输出评估中使用 LLM-as-Judge 对开放性输出评分，不做 every-step LLM eval。

#### Scenario: 开放性输出评估
- **WHEN** 场景的预期输出为开放性描述（如 "回答应包含合理的建议"）
- **THEN** 系统调用 Judge LLM 对最终输出评分（1-5 分），提供评分理由，中间步骤不调用 LLM eval

### Requirement: 评测数据集版本管理
系统 SHALL 支持评测数据集的版本化存储，支持加载、过滤、采样、版本对比。

#### Scenario: 版本对比
- **WHEN** 使用 v1 和 v2 两个版本的评测数据集分别运行
- **THEN** 输出对比报告，展示各指标变化

### Requirement: 从生产 Trace 生成评测用例
系统 SHALL 支持从执行 trace 自动提取并转化为评测场景。

#### Scenario: Trace → Eval Case
- **WHEN** 选择一条成功的 trace 并执行转化
- **THEN** 系统自动提取用户输入、实际 tool call 序列、最终输出，生成可编辑的评测场景
