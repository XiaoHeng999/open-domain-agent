## MODIFIED Requirements

### Requirement: 工具错误四分类
系统 SHALL 将工具调用错误分为四类：ParameterError（参数格式/类型/缺失）、RetrievalError（检索结果不全或召回差）、ServiceError（服务不可用或超时）、ParseError（返回结果无法解析）。ParameterError 在 `ToolRegistry.execute()` 的 `cast_params()` 和 `validate_params()` 阶段触发，无需等到实际执行后。

#### Scenario: 参数校验阶段触发 ParameterError
- **WHEN** `validate_params()` 检测到 `{"path": "file.txt"}` 缺少 required 字段 `content`
- **THEN** 在 `execute()` 调用前即返回 ParameterError，不执行工具 handler

#### Scenario: cast_params 阶段类型转换失败
- **WHEN** `cast_params()` 无法将 `"abc"` 转为 integer 类型
- **THEN** 触发 ParameterError，提示参数类型不匹配

#### Scenario: 执行阶段触发 ServiceError
- **WHEN** `web_search` 工具调用 Brave API 返回 HTTP 503
- **THEN** 工具 execute() 抛出 ServiceError

#### Scenario: 检索不全扩展查询
- **WHEN** 工具调用返回 RetrievalError（搜索结果为空或远少于预期）
- **THEN** 系统执行确定性恢复策略链：同义词替换 → 放宽过滤 → 降级缓存，逐步扩展

#### Scenario: 结果不可解析换格式
- **WHEN** 工具调用返回 ParseError（预期 JSON 但收到 HTML）
- **THEN** 尝试切换输出格式参数重试，或使用 LLM 辅助解析

### Requirement: 确定性恢复策略
系统 SHALL 为每种错误类型提供确定性的恢复策略链，不依赖 LLM 判断恢复方式。恢复策略在 `ToolRegistry.execute()` 内部执行，对 ReAct 循环透明。

#### Scenario: 策略链顺序执行
- **WHEN** 一次工具调用触发 RetrievalError
- **THEN** 系统按预设策略链依次执行：expand_query → relax_filters → use_cache → report_to_agent，直到某个策略成功或链耗尽

#### Scenario: 策略链耗尽上报
- **WHEN** 所有恢复策略均失败
- **THEN** 系统将错误信息和已尝试策略汇总报告给 Agent，由 Agent 的 ReAct reflection 决定下一步

### Requirement: 自定义恢复策略注册
系统 SHALL 支持开发者注册自定义恢复策略，通过标准接口接入策略链。

#### Scenario: 注册自定义策略
- **WHEN** 开发者注册名为 "retry_with_different_model" 的策略
- **THEN** 该策略可用于任何错误类型的策略链配置中

### Requirement: 错误恢复 Trace
系统 SHALL 为每次错误恢复生成 trace，包含错误分类、尝试的策略、每次策略结果、最终状态。

#### Scenario: 恢复过程 trace
- **WHEN** 一次错误恢复完成
- **THEN** trace 包含 original_error（含分类）、recovery_attempts（策略名+结果）、final_status、total_recovery_latency_ms
