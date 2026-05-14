## Why

Agent 在真实环境中失败不是例外而是常态。当前 open_agent 的约束层（safety + permission）和恢复层（recovery + checkpoint）已经相当完善，但**校验层存在结构性缺口**：工具输出只靠 `"Error:"` 前缀判断成败，没有结构化的输出校验；TOOL_AFTER Hook 无法阻断坏结果；部分配置约束（max_children、auto_timeout）定义了但未执行。这些缺口意味着 agent 可能把无意义或错误的结果当作成功继续往下走，最终产出低质量回答。需要在运行时增加输出质量门控，并补齐约束执行的缺口。

## What Changes

- 新增工具输出校验机制：工具可声明 `output_schema`（JSON Schema），执行后自动校验返回值结构；支持可选的 `validate_output()` 方法做语义级检查（如：搜索结果不为空、文件确实被创建）
- 新增 TOOL_AFTER Hook 阻断能力：`TOOL_AFTER` Hook 返回 `blocked=True` 时，结果被拒绝并触发 recovery 路径，而非仅做审计日志
- 执行 `max_children` 子 Agent 嵌套深度限制：在 `SubagentManager` 中实际检查并拒绝超过深度限制的嵌套调用
- 执行 `SandboxConfig.auto_timeout`：在 sandbox 执行中实际应用自动超时
- 将异常检测从被动升级为主动：当工具循环或重复错误达到阈值时，终止当前执行而非仅记录

## Capabilities

### New Capabilities
- `output-quality-gate`: 工具输出结构校验（output_schema）+ 语义级质量检查（validate_output）+ TOOL_AFTER 阻断后触发 recovery 的完整管线

### Modified Capabilities
- `hook-system`: 扩展 TOOL_AFTER 事件支持 `blocked=True` 阻断语义，拒绝不合格结果
- `subagent-manager`: 在 `spawn` 流程中实际执行 `max_children` 深度检查，超限时返回结构化错误
- `tool-health-tracking`: 异常检测从被动记录升级为主动终止——工具循环/重复错误达阈值时终止执行
- `security-sandbox`: 执行 `auto_timeout`；补齐 Docker 沙箱的 `restore()` 实现

## Impact

- `src/open_agent/tools/base.py` — Tool ABC 新增 `output_schema` 属性和 `validate_output()` 方法
- `src/open_agent/hooks/manager.py`, `builtin.py` — HookResult 支持 TOOL_AFTER 阻断
- `src/open_agent/agent/react.py` — ReAct 循环处理 TOOL_AFTER 阻断 + 主动异常终止
- `src/open_agent/subagent/manager.py` — 执行 max_children 检查
- `src/open_agent/sandbox/docker.py` — 实现 restore
- `src/open_agent/sandbox/factory.py` — 执行 auto_timeout
- `src/open_agent/middleware.py` — 新增 OutputValidationMiddleware
- `src/open_agent/monitoring/collector.py` — 异常检测升级为主动阻断
- 所有内置工具 — 补充 output_schema 声明
