## 1. 激活结构化日志

- [x] 1.1 在 `runtime.py` 的 `on_start()` 中调用 `setup_structured_logging()`，确保 logger 在运行时初始化
- [x] 1.2 在 `trace.py` 的 `setup_structured_logging()` 中添加 `trace_id` 支持到 log filter，使每条日志可关联到当前 trace

## 2. Routing 管线日志

- [x] 2.1 在 `routing/router.py` 的 `_route_keyword()` 中，为 complexity 判定结果添加 `logger.info()` （记录 complexity、confidence、method）
- [x] 2.2 在 `routing/router.py` 的 `_route_keyword()` 中，为 domain 路由结果添加 `logger.info()` （记录 domain、score）
- [x] 2.3 在 `routing/router.py` 的 `_route_keyword()` 中，为 intent 解析结果添加 `logger.info()` （记录 intent、slots）
- [x] 2.4 在 `routing/router.py` 的 `_route_unified()` 中，为统一路由结果添加 `logger.info()` （记录 domain、complexity、intent）

## 3. ReAct 循环日志

- [x] 3.1 在 `agent/react.py` 的 `run()` 主循环中，为每次迭代开始添加 `logger.info()` （记录 iteration number）
- [x] 3.2 在 `agent/react.py` 的 `_think_and_act()` 中，为 LLM 返回结果添加 `logger.info()` （记录是否有 tool calls、tool 名称列表）
- [x] 3.3 在 `agent/react.py` 的 `_execute_action()` 中，为工具执行添加 `logger.info()` （记录 tool name、args 摘要、耗时、结果长度）
- [x] 3.4 在 `agent/react.py` 的 `run()` 中，为最终回答添加 `logger.info()` （记录 iteration count、总耗时）

## 4. Runtime 执行摘要日志

- [x] 4.1 在 `runtime.py` 的 `run()` 末尾添加 `logger.info()` 执行摘要（记录 trace_id、domain、intent、steps、duration_ms）

## 5. Rich 实时追踪展示

- [x] 5.1 修改 `cli.py` chat 循环，在 `runtime.run()` 返回后打印 Rich 样式的 routing 摘要行（complexity、domain、intent、duration）
- [x] 5.2 增强 `cli.py` 中已有的 Step 展示逻辑，在每步显示中添加工具名称和耗时信息
