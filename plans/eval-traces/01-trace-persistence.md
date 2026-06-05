# Issue 01: Trace 持久化 + agent trace 命令

## What to build

让 Trace 具备磁盘持久化能力，使 `agent trace <id>` 命令真正可用。

端到端行为：当 Agent 执行任务时，runtime 在内存中创建 Trace 和 Span（现有逻辑不变）。当 runtime 关闭（`on_stop`）时，所有 trace 自动写入 `{trace_dir}/{trace_id}.json`。之后用户可以通过 `agent trace <trace_id>` 查看任意一次对话的完整执行链路，包括路由决策、工具调用参数和结果、ReAct 迭代详情。

持久化时机选择 `on_stop` 而非每次 `run()` 后立即写入，减少 IO 频次，确保 session 内所有 trace 完整保存。持久化失败不阻塞正常关闭（try/except 包裹）。

Config 中的 `TraceConfig` 已有 `store_traces: bool = True` 和 `trace_dir: str = ".open_agent/traces"` 字段，需要让代码真正读取并使用这些配置。同时增加环境变量 `OPEN_AGENT_TRACE_DIR` 和 `OPEN_AGENT_STORE_TRACES` 的覆盖支持。

## Acceptance criteria

- [ ] TraceManager 新增 `persist_trace(trace_id)` 异步方法，将 trace JSON 写入 `{trace_dir}/{trace_id}.json`
- [ ] TraceManager 新增 `load_trace(trace_id)` 方法，从磁盘读取并返回 Trace 对象
- [ ] TraceManager 新增 `list_persisted_traces()` 方法，扫描 trace_dir 返回所有 trace_id
- [ ] AgentRuntime.on_stop 中调用 persist_trace 持久化所有内存中的 trace
- [ ] `OPEN_AGENT_TRACE_DIR` 环境变量可覆盖 trace_dir 配置
- [ ] `agent trace <id>` 命令能正常输出持久化的 trace JSON
- [ ] 持久化失败时进程正常退出，不抛异常
- [ ] 测试覆盖：persist → load 往返正确性、目录自动创建、load 不存在的 id 返回 None

## Blocked by

None — 可立即开始

## User stories

- #1 trace 在进程退出后仍然可查
- #2 `agent trace <trace_id>` 正常工作
- #5 trace 存储路径可通过环境变量配置
