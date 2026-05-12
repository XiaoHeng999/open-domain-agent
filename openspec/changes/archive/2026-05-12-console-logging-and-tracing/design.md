## Context

open_agent 已有 trace.py 中的 Span/Trace/TraceManager 模型，以及在各模块（routing、react、runtime）中创建 span 的代码。但 `setup_structured_logging()` 从未被调用，所有日志使用 Python 默认配置，运行时无可见输出。

当前使用的 logger 名称统一为 `"open_agent"`，Rich 已作为 console 输出依赖引入。

## Goals / Non-Goals

**Goals:**
- 激活 `setup_structured_logging()`，让所有 `logger.info()` 调用输出带时间戳的结构化日志
- 在 RoutingPipeline 中记录 complexity/domain/intent 三阶段决策及耗时
- 在 ReActLoop 中记录每次迭代的 think → action → observation 过程
- 在 Runtime.run() 中记录端到端执行摘要
- 在 CLI chat 循环中用 Rich 实时打印彩色追踪摘要（routing 结果 + ReAct 步骤）

**Non-Goals:**
- 不做 OTel 导出或 JSON trace 文件持久化（方案 C，后续再做）
- 不改动 Span/Trace 数据模型本身
- 不新增外部依赖

## Decisions

### 1. 复用已有 `setup_structured_logging()`

**选择**：直接激活 trace.py 中已有的 `setup_structured_logging()`，在 `runtime.on_start()` 中调用。

**替代方案**：重新写一套 logging 配置。**否决原因**：已有代码完全可用，重写是浪费。

### 2. 日志输出格式：简洁单行 + Rich 摘要双层

**选择**：
- **底层**：`logger.info()` 输出结构化单行日志（方案 A），写到 stderr
- **表层**：CLI 层用 Rich console 打印彩色追踪面板（方案 B），写到 stdout

**替代方案**：只用 Rich 或只用 logger。**否决原因**：双层方案兼顾机器可读（grep/log aggregation）和人类可读（实时交互）。

### 3. 日志粒度：每个关键决策点一条

**选择**：在以下节点各添加一条 `logger.info()`：
- `RoutingPipeline.route()` — complexity 判定结果
- `RoutingPipeline.route()` — domain 路由结果
- `RoutingPipeline.route()` — intent 解析结果
- `ReActLoop.run()` — 每次迭代开始/结束
- `ReActLoop._think_and_act()` — LLM 调用结果（是否有 tool calls）
- `ReActLoop._execute_action()` — 工具执行结果和耗时
- `Runtime.run()` — 端到端摘要（trace_id, steps, duration）

**替代方案**：每行代码都加日志。**否决原因**：过于冗余，反而降低可读性。

### 4. Rich 追踪展示：复用现有 cli.py 中的 console

**选择**：在 `cli.py` 的 chat 循环中，路由完成后打印一行 routing 摘要，ReAct 完成后打印步骤摘要（已有 Step 展示逻辑，增强即可）。

## Risks / Trade-offs

- **[日志过多影响交互]** → 用 `logging.INFO` 级别控制，后续可加 `--verbose` flag 切换 `DEBUG`
- **[JSON 格式日志在终端不好读]** → Rich 层提供人类友好的摘要，JSON 日志主要供 `> file.log` 重定向使用
- **[性能开销]** → `logger.info()` 本身开销极低（微秒级），不影响 agent 执行性能
