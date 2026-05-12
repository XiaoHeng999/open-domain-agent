## Why

当前 open_agent 的 trace.py 已有完整的 Span/Trace/TraceManager 数据模型，但 `setup_structured_logging()` 从未被调用，所有 span 在运行时静默创建、无人感知。用户无法在控制台看到 intent 识别结果、路由决策、ReAct 循环每一步的执行细节，调试和开发体验差。

## What Changes

- **激活 `setup_structured_logging()`**：在 Runtime 启动时调用，为 `"open_agent"` logger 配置结构化 JSON 日志输出到 console
- **在路由管线（RoutingPipeline）中添加日志**：记录 complexity 判定、domain 路由、intent 解析的输入/输出/耗时
- **在 ReAct 循环中添加日志**：记录每次迭代的 think → action → observation 全过程，包括工具调用、参数摘要、耗时
- **在 Runtime.run() 中添加日志**：记录完整执行管线（route → skills → prompt → react → response）的端到端摘要
- **在 CLI chat 循环中用 Rich 打印追踪摘要**：将 routing 结果和 ReAct 步骤以彩色、结构化方式实时展示给用户

## Capabilities

### New Capabilities
- `console-observability`: 激活结构化日志 + Rich 实时追踪面板，覆盖 routing、intent、react 三大模块

### Modified Capabilities
（无 spec 级别的需求变更，所有改动均为实现层增强）

## Impact

- **代码改动**：`trace.py`（激活 logging）、`routing/router.py`（加日志）、`agent/react.py`（加日志）、`runtime.py`（加日志 + 调用 setup）、`cli.py`（Rich 追踪展示）
- **依赖**：无新依赖，Rich 已在项目中使用
- **兼容性**：纯增量改动，不破坏现有 API 和行为
