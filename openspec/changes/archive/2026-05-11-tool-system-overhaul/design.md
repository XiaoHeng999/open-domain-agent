## Context

open_agent 当前工具系统采用 structured JSON output 模拟工具调用——LLM 输出 `{thought, tool_name, args}` JSON，由 `_tool_schema()` 方法注入工具列表。这种方式存在可靠性差、Token 浪费、缺少参数校验等问题。安全治理框架（SafetyManager、HITL）已实现但未接入执行路径。仅有一个 `todo` 工具定义且从未注册。

参考 nanobot（HKUDS）的 Tool ABC + 按域分组 + JSON Schema 校验的组织模式，结合本项目的 Anthropic provider 优势，重构为原生 `tool_use` 调用体系。

**当前架构关键文件：**
- `src/open_agent/agent/react.py` — ReAct 循环，`_think_and_act()` 用 `complete_structured()`
- `src/open_agent/model.py` — Provider，`AnthropicProvider.complete()` 不支持 tools 参数
- `src/open_agent/registry.py` — `ToolRegistry`，基于 `ToolEntry(handler, schema)` 的函数式注册
- `src/open_agent/decorators.py` — `@tool_schema` 从函数签名生成 schema
- `src/open_agent/tools/todo.py` — 唯一工具，用 `@tool_schema` 装饰器
- `src/open_agent/base.py` — `ToolExecutor` ABC（未使用）

**nanobot 参考架构：**
- `base.py` — `Tool` ABC + `Schema` ABC + `tool_parameters()` 装饰器
- `registry.py` — `ToolRegistry`，`get_definitions()` 输出 function-calling 格式
- `filesystem.py` / `shell.py` / `web.py` — 按域分组的工具类

## Goals / Non-Goals

**Goals:**
- 采用 Anthropic 原生 `tool_use` API 格式进行工具调用，废弃 structured JSON 模拟
- 实现 Tool ABC 基类，包含 `cast_params()` + `validate_params()` 参数校验管道
- 实现 7 个核心工具 + 保留升级 `todo` 工具，按域分组到独立文件
- 实现 `scan_builtin_tools()` 自动发现并注册内置工具
- 将 SafetyManager 安全检查接入 `_execute_action()` 执行路径
- 工具执行全面异步化，支持 async handler
- 消除工具 schema 双重注入，统一为 `to_schema()` 生成 Anthropic 格式
- 应用 `max_tool_result_tokens` 截断工具输出
- 保留 ToolRegistry 的 snapshot/restore、tag 过滤等已有能力

**Non-Goals:**
- 不实现 MCP 工具发现（`tools/list`），保持 MCP 集成的独立变更空间
- 不实现沙箱隔离（Daytona/Docker），保持 security-sandbox spec 的独立实现空间
- 不实现工具热加载，启动时一次性扫描即可
- 不实现并行工具执行（`concurrency_safe` / `exclusive`），单线程顺序执行
- 不实现 `image_generation`、`cron`、`spawn` 工具（按需求排除）

## Decisions

### D1: 采用 Anthropic `tool_use` 原生格式替代 structured JSON

**选择：** 使用 Anthropic Messages API 的 `tools` 参数 + `tool_use` content block + `tool_result` message format。

**理由：**
- 原生 `tool_use` 由 API 保证 JSON 结构正确，无需 LLM 自律输出合法 JSON
- `tool_choice` 参数可控制是否强制调用工具
- `stop_reason: "tool_use"` 天然标记循环终止条件，无需 `direct_answer` sentinel
- 减少 Token 消耗——schema 通过 `tools` 参数传递，不在 system prompt 中重复

**替代方案：**
- 保持 structured JSON 但改进校验 → 可靠性天花板低，LLM 偶尔输出非法 JSON
- 使用 OpenAI function-calling 格式 → 与 Anthropic provider 不匹配，需要格式转换层

**实现要点：**
- `AnthropicProvider` 新增 `complete_with_tools(messages, tool_definitions)` 方法
- 返回解析后的 `AssistantMessage`，包含 `content`（text blocks）和 `tool_calls`（tool_use blocks）
- `tool_result` 作为 `role: "user"` message 中的 `tool_result` content block 回传

### D2: Tool ABC 基类设计（参考 nanobot 模式）

**选择：** 采用 nanobot 的 `Tool` ABC 模式——抽象属性 `name`/`description`/`parameters` + 抽象方法 `async execute(**kwargs)` + 具体方法 `cast_params()`/`validate_params()`/`to_schema()`。

**理由：**
- 类型安全的参数校验在执行前拦截错误，而非让 Python TypeError 暴露
- `cast_params()` 处理 LLM 常见输出怪癖（string→int、string→bool），提高容错性
- `to_schema()` 统一输出 Anthropic `tool_use` 格式，消除双重注入
- `read_only` 属性为未来并发执行优化预留接口

**替代方案：**
- 保持函数式 `@tool_schema` 装饰器 → 无法强制 `cast_params`/`validate_params` 管道
- 使用 dataclass 而非 ABC → 丧失接口约束力

**实现要点：**
- `Tool` 继承 `BaseComponent`，保持生命周期兼容
- `to_schema()` 输出 Anthropic 格式：`{"name": ..., "description": ..., "input_schema": {...}}`
- `cast_params()` 参考 nanobot 的 `_TYPE_MAP` + `_BOOL_TRUE`/`_BOOL_FALSE`
- `validate_params()` 参考 nanobot 的 `Schema.validate_json_schema_value()` 递归校验
- `execute()` 返回 `str | list[dict]`（字符串或 content blocks）

### D3: 工具按域分组文件组织

**选择：** 按域分组到独立文件：`filesystem.py`（4个工具）、`shell.py`（1个）、`web.py`（2个）、`todo.py`（保留升级）。

**理由：**
- 与 nanobot 一致的代码组织模式
- 每个文件包含同一域的多个工具类，避免文件爆炸
- 每个工具类可持有自己的配置（workspace 路径、API key 等）

**实现要点：**
```
src/open_agent/tools/
  __init__.py       # 导出 Tool, ToolRegistry, scan_builtin_tools
  base.py           # Tool ABC, Schema ABC, tool_parameters 装饰器
  registry.py       # ToolRegistry 重构版
  filesystem.py     # ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
  shell.py          # ExecTool
  web.py            # WebSearchTool, WebFetchTool
  todo.py           # TodoTool（升级版，继承 Tool ABC）
```

### D4: SafetyManager 接入执行路径

**选择：** 在 `ToolRegistry.execute()` 中统一调用 SafetyManager，形成 actual enforcement。

**理由：**
- 当前 SafetyManager 的 check_command/check_url/check_path/approve_operation 全部未接入
- 执行路径是唯一能确保每次工具调用都经过安全检查的位置

**实现要点：**
- Tool 基类新增 `safety_checks` 属性（返回需要执行的检查类型列表）
- `ExecTool` → `["command"]`
- `WebSearchTool`/`WebFetchTool` → `["url"]`
- `ReadFileTool`/`WriteFileTool`/`EditFileTool` → `["path"]`
- `ToolRegistry.execute()` 在 `cast_params` 前调用 SafetyManager
- 安全检查不通过时返回错误字符串（不抛异常），LLM 可据此调整

### D5: 废弃 `@tool_schema` 装饰器，由 Tool ABC 替代

**选择：** 新工具统一继承 `Tool` ABC 并实现 `parameters` 属性，废弃 `@tool_schema` 装饰器。

**理由：**
- Tool ABC 提供 `cast_params`/`validate_params` 管道，装饰器无法提供
- ABC 模式强制工具实现者遵循统一接口
- 装饰器模式只能生成 schema，无法承载安全检查、异步执行等横切关注点

**迁移策略：**
- `todo.py` 从 `@tool_schema` 函数改为 `TodoTool(Tool)` 类
- MCP 注册的远程工具保持函数式，通过 `FunctionTool` 适配器包装为 Tool 实例
- `decorators.py` 保留但标记 deprecated，不删除（向后兼容）

### D6: 工具结果 Token 截断

**选择：** 在 `ToolRegistry.execute()` 返回前截断结果字符串。

**理由：**
- `MemoryConfig.max_tool_result_tokens` 已定义（默认 2000）但从未使用
- 大工具输出（如读取大文件）会撑爆上下文窗口

**实现要点：**
- 使用简单的字符截断（~4 chars/token → `max_tokens * 4`）
- 截断时追加 `"\n...[truncated]"` 提示

## Risks / Trade-offs

**[R1] Anthropic-only 格式锁定** → 缓解：`Tool.to_schema()` 可扩展为根据 provider 类型输出不同格式；OpenAI provider 可添加格式转换适配器。当前项目默认 DeepSeek provider 使用 OpenAI-compatible API，需同时支持 OpenAI function-calling 格式。

**[R2] 大量新文件增加维护负担** → 缓解：每个工具文件独立，按域隔离，修改一个工具不影响其他。Tool ABC 约束统一模式，降低认知成本。

**[R3] 安全检查阻塞工具执行可能影响用户体验** → 缓解：安全级别可配置（strict/permissive/off），permissive 模式下只阻止 dangerous 操作。

**[R4] `todo` 工具迁移可能破坏现有测试** → 缓解：保持 `todo_handler` 函数签名不变作为内部实现，`TodoTool` 类包装调用。

**[R5] Anthropic provider 的 `complete_with_tools` 需要处理 tool_use 和 text 混合 content block** → 缓解：参考 Anthropic SDK 文档的 multi-content-block 处理模式，按 block type 分发。
