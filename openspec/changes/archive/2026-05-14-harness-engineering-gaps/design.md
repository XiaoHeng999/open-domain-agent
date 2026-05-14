## Context

open_agent 当前在约束层（safety + permission + sandbox）和恢复层（recovery strategies + checkpoint + circuit breaker）已有完善的实现。但校验层存在结构性缺口：

1. **输出无门控**：工具返回值仅靠 `"Error:"` 前缀判断成败，没有结构化的输出校验。`ToolResult.success` 提供了信号层，但没有内容层的质量检查。
2. **TOOL_AFTER 只能看不能拦**：Hook 系统的 `blocked=True` 只对 `TOOL_BEFORE` 生效，`TOOL_AFTER` 仅做审计日志。
3. **配置约束定义但未执行**：`max_children`、`auto_timeout` 在 Pydantic 模型中定义但运行时未检查。
4. **异常检测是被动**：`AnomalyDetector` 只记录和生成回避提示，不终止当前执行。
5. **Docker 沙箱 restore 缺失**：snapshot 可以 commit 容器为镜像，但 restore 未实现。

当前架构关键路径：`ToolRegistry.execute()` → `cast_params` → `validate_params` → `SafetyMiddleware` → `PermissionMiddleware` → `TruncateMiddleware` → `ExecuteMiddleware`。输出仅在 `TruncateMiddleware` 做截断，无质量检查。

## Goals / Non-Goals

**Goals:**
- 工具执行后能自动校验输出是否符合预期结构和语义
- TOOL_AFTER Hook 能阻断不合格结果并触发 recovery
- max_children 嵌套深度限制在运行时实际执行
- auto_timeout 在沙箱执行中实际应用
- 异常检测从被动记录升级为主动终止
- Docker 沙箱 restore 功能补齐

**Non-Goals:**
- 不改变现有的 Safety / Permission 中间件行为
- 不引入 LLM 级别的输出质量评估（成本太高，后续独立迭代）
- 不改变 checkpoint 系统的设计
- 不增加新的外部依赖

## Decisions

### D1: 输出校验采用 opt-in 模式，工具可声明 output_schema

**选择**：在 `Tool` ABC 中新增 `output_schema` 类属性（JSON Schema）和 `validate_output()` 方法。默认为 None（不做校验）。新增 `OutputValidationMiddleware` 插入到 `ExecuteMiddleware` 之后。

**备选**：A) 强制所有工具声明 output_schema（迁移成本高）；B) 在 ReAct 循环中做通用启发式检查（不够精确）。

**理由**：opt-in 模式让现有工具零改动即可工作，新工具和高风险工具可选择性声明校验规则。放在中间件层而非工具内部，保持了关注点分离。

### D2: TOOL_AFTER 阻断通过 HookResult.blocked 扩展实现

**选择**：扩展 `HookResult` 的 `blocked` 字段语义，使其在 `TOOL_AFTER` 事件中也有效。`TOOL_AFTER` 返回 `blocked=True` 时，结果被替换为错误消息，ReAct 循环将其视为工具失败并走 recovery 路径。

**备选**：A) 新增 `TOOL_VALIDATE` 事件类型；B) 在中间件链末尾加校验中间件，不依赖 Hook。

**理由**：复用现有 Hook 基础设施，减少新概念。Hook 已有优先级、短路等机制，扩展语义比新增事件类型成本低。

### D3: max_children 通过 parent_id 追踪执行

**选择**：`SubagentManager.create_subagent()` 接收 `parent_id` 参数，维护 `children_by_parent: dict[str, set]` 映射。创建前检查 `len(children_by_parent[parent_id]) >= max_children`。

**备选**：A) 全局计数器（无法区分父代理）；B) 在 ReAct 循环中检查（耦合过深）。

**理由**：`parent_id` 已在 `SubagentTool` 调用上下文中可用（通过 `agent_id`），实现简单且精确。

### D4: auto_timeout 通过 asyncio.wait_for 包装沙箱执行

**选择**：在 `SubprocessSandbox.exec()` 和 `DockerSandbox.exec()` 中用 `asyncio.wait_for(coro, timeout=config.auto_timeout)` 包装，超时抛出 `asyncio.TimeoutError`。

**备选**：A) 在 ReAct 循环层统一超时（粒度太粗）；B) 单独的超时中间件（增加复杂性）。

**理由**：超时是沙箱执行的天然约束，放在最底层最合理。复用 `asyncio.wait_for` 零额外依赖。

### D5: 异常检测主动终止通过 ReAct 循环集成实现

**选择**：在 ReAct 循环的每轮迭代末尾调用 `AnomalyDetector.detect()`，如果检测到工具循环（同工具 ≥4 次）或重复错误（同错误 ≥3 次），设置 `should_terminate=True`。

**备选**：A) 在中间件中终止（无法感知跨步骤模式）；B) 独立的 watchdog 协程（增加复杂性）。

**理由**：异常是跨步骤的模式，ReAct 循环是唯一个体能看到完整执行历史的层级。

## Risks / Trade-offs

- **[输出校验性能开销]** → 仅对声明了 output_schema 的工具触发校验，默认无开销。Schema 校验是 O(n) 级别，n 为输出字段数。
- **[TOOL_AFTER 阻断可能导致无限 recovery 循环]** → recovery 有最大重试次数限制（3 次），且工具降级机制会在 3 次失败后标记降级，双重保护。
- **[max_children 的 parent_id 追踪需要正确清理]** → 子代理完成/失败时从 `children_by_parent` 中移除，`stop_all()` 时批量清理。
- **[auto_timeout 可能截断长时间合法操作]** → 默认 300 秒对大多数操作足够；可通过配置调整。
- **[Docker restore 可能因镜像层叠加变慢]** → restore 后建议立即做一次新 snapshot 替代旧 snapshot，保持镜像层薄。
