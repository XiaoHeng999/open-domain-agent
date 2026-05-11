## Why

当前工具系统采用 structured JSON output 模拟工具调用（LLM 输出 `{thought, tool_name, args}` JSON），而非使用 Anthropic 原生 `tool_use` API。这导致：可靠性差（依赖 LLM 自律输出合法 JSON）、Token 浪费（工具 schema 在 prompt 中重复注入两次）、缺少参数校验（LLM args 直接 `**kwargs` 展开）、安全层未接入执行路径、仅 1 个工具注册且无自动发现机制。需要全面重构为基于 Anthropic `tool_use` 格式的原生工具调用体系。

## What Changes

- **BREAKING** 废弃 structured JSON 模拟机制（`_tool_schema()` + `complete_structured()`），改用 Anthropic `tool_use` / `tool_result` 原生 message format
- **BREAKING** 重构 `ToolRegistry` 和 `Tool` 基类，采用 nanobot 风格的 ABC + JSON Schema 参数校验 + `cast_params()` 类型强转
- 新增 7 个核心工具实现：`read_file`、`write_file`、`edit_file`、`list_dir`、`exec`、`web_search`、`web_fetch`（参考 nanobot 组织方式，按域分组到 `filesystem.py`、`shell.py`、`web.py`）
- 保留并升级 `todo` 工具，纳入统一工具体系
- 新增工具自动发现机制（`scan_builtin_tools()`），对标 skills 系统的 `scan_builtin_skills()`
- 将 `SafetyManager` 安全检查接入 `_execute_action()` 执行路径，使其真正生效
- 实现 `cast_params()` + `validate_params()` 参数校验管道，在调用 handler 前强制校验
- 工具执行全面异步化，修复 async handler 未被 await 的问题
- 消除工具 schema 双重注入，统一由 `to_schema()` 生成 Anthropic function-calling 格式定义
- 应用 `max_tool_result_tokens` 配置，截断过长工具输出

## Capabilities

### New Capabilities
- `tool-base-abc`: Tool 抽象基类设计——含 `name`、`description`、`parameters`、`read_only`、`execute()` 等 ABC 接口，`cast_params()` 类型强转，`validate_params()` JSON Schema 校验，`to_schema()` Anthropic 格式输出
- `tool-filesystem`: 文件系统工具组——`read_file`、`write_file`、`edit_file`、`list_dir` 四个工具，统一工作区路径限制
- `tool-shell`: Shell 执行工具——`exec` 工具，异步子进程执行，超时控制，输出截断
- `tool-web`: Web 工具组——`web_search`（Brave Search API）、`web_fetch`（URL 内容抓取），SSRF 防护集成
- `tool-registry-v2`: 重构后的 ToolRegistry——自动发现、Anthropic 格式 schema 导出、批量注册、异步执行分发
- `tool-native-calling`: ReAct 循环中原生 tool_use 调用——替换 structured JSON 为 Anthropic tool_use message format，tool_result 回传

### Modified Capabilities
- `tool-error-recovery`: 工具错误恢复策略需适配新的 Tool ABC 和异步执行管道，校验错误在 cast/validate 阶段触发而非执行后
- `security-sandbox`: SafetyManager 安全检查必须接入 `_execute_action()` 执行路径，形成 actual enforcement 而非 declarative-only
- `mcp-integration`: MCP 工具注册需输出 Anthropic 格式 schema，MCP server 发现需补齐 `tools/list` 调用

## Impact

**核心代码变更：**
- `src/open_agent/agent/react.py` — ReAct 循环调用方式从 `complete_structured()` 改为原生 `tool_use` message format
- `src/open_agent/model.py` — Anthropic provider 需支持 `tools` 参数和 `tool_use`/`tool_result` content block
- `src/open_agent/registry.py` — ToolRegistry 重写，新增 `get_definitions()` 输出 Anthropic 格式，执行分发含校验和安全检查
- `src/open_agent/decorators.py` — `@tool_schema` 适配新 Tool ABC 或废弃（由基类替代）
- `src/open_agent/tools/` — 新增 `base.py`、`filesystem.py`、`shell.py`、`web.py`，保留升级 `todo.py`
- `src/open_agent/runtime.py` — 新增 `scan_builtin_tools()` 自动发现并注册内置工具
- `src/open_agent/safety/` — 接入执行路径
- `src/open_agent/prompt/segments.py` — 消除 `ToolListSegment` 双重注入

**依赖变更：**
- 新增 `httpx`（异步 HTTP 客户端，用于 web 工具）
- Anthropic SDK 需确保支持 `tools` 参数（当前已支持）

**测试影响：**
- `tests/test_harness.py`、`tests/test_agent.py`、`tests/test_mcp.py` 需适配新接口
