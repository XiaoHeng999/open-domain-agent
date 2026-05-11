## 1. Tool ABC 基类与基础设施

- [x] 1.1 创建 `src/open_agent/tools/base.py`：实现 `Tool` ABC（抽象属性 name/description/parameters、抽象方法 async execute、具体方法 cast_params/validate_params/to_schema、属性 read_only）
- [x] 1.2 在 `base.py` 中实现 `cast_params()` 类型强转管道（str→int、str→bool、null→空字符串、递归嵌套对象）
- [x] 1.3 在 `base.py` 中实现 `validate_params()` JSON Schema 递归校验（type/enum/required/min/max/minLength/maxLength/minItems/maxItems/嵌套）
- [x] 1.4 在 `base.py` 中实现 `to_schema()` 输出 Anthropic tool_use 格式：`{"name", "description", "input_schema"}`
- [x] 1.5 实现 `FunctionTool` 适配器类，将函数式 handler 包装为 Tool ABC 实例（用于 MCP 远程工具兼容）
- [x] 1.6 编写 `tests/test_tool_base.py`：验证 cast_params/validate_params/to_schema 的各种场景

## 2. ToolRegistry 重构

- [x] 2.1 重写 `src/open_agent/tools/registry.py`（或 `src/open_agent/registry.py`）：内部存储改为 `dict[str, Tool]`，保留 register/unregister/get/has/snapshot/restore 接口
- [x] 2.2 实现 `ToolRegistry.execute(name, params)` 异步执行方法，含三阶段管道：cast_params → validate_params → await execute
- [x] 2.3 在 execute 管道中集成 SafetyManager 安全检查：根据工具的 safety_checks 属性调用对应的 check_command/check_url/check_path
- [x] 2.4 在 execute 管道中实现工具结果 Token 截断（基于 max_tool_result_tokens 配置）
- [x] 2.5 实现 `get_definitions()` 方法：返回所有注册工具的 `to_schema()` 列表
- [x] 2.6 实现 `scan_builtin_tools(registry, config)` 函数：自动扫描并注册所有内置工具
- [x] 2.7 编写 `tests/test_tool_registry_v2.py`：验证注册、执行管道、校验、截断、snapshot/restore

## 3. ModelProvider 扩展——原生 tool_use 支持

- [x] 3.1 定义 `ToolCall` 和 `ToolCallResponse` 数据结构（在 `model.py` 或新文件 `types.py` 中）
- [x] 3.2 在 `ModelProvider` ABC 中新增 `complete_with_tools(messages, tool_definitions)` 抽象方法
- [x] 3.3 实现 `AnthropicProvider.complete_with_tools()`：使用 `client.messages.create(tools=...)` 调用 API，解析 tool_use content block
- [x] 3.4 实现 `OpenAIProvider.complete_with_tools()`：转换 Anthropic 格式 tools 为 OpenAI function-calling 格式，统一返回 ToolCallResponse
- [x] 3.5 实现 `DeepSeekProvider.complete_with_tools()`：继承 OpenAIProvider 实现
- [x] 3.6 标记 `complete_structured()` 为 deprecated，添加 DeprecationWarning
- [x] 3.7 编写 `tests/test_provider_tools.py`：验证 Anthropic/OpenAI provider 的 tool_use 调用和响应解析

## 4. ReAct 循环适配——原生 tool_use 消息流

- [x] 4.1 重构 `ReActLoop._think_and_act()`：调用 `provider.complete_with_tools(messages, tool_definitions)` 替代 `complete_structured()`
- [x] 4.2 移除 `_tool_schema()` 方法（不再需要 structured JSON schema 描述）
- [x] 4.3 重构 `_build_messages()`：不再注入工具描述和 JSON 格式指令，改用 tool_use/tool_result content block 格式
- [x] 4.4 实现 tool_result 回传逻辑：工具执行结果构造为 `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": ..., "content": result}]}`
- [x] 4.5 修改停止条件：从 `tool_name == "direct_answer"` 改为 `stop_reason == "end_turn"`（LLM 不调用工具时自然停止）
- [x] 4.6 保留重复动作检测和 max_iterations 硬限制
- [x] 4.7 编写 `tests/test_react_tool_use.py`：验证完整 tool_use/tool_result 消息循环

## 5. 文件系统工具实现

- [x] 5.1 创建 `src/open_agent/tools/filesystem.py`：实现 `ReadFileTool`（支持 offset/limit 分页、文件不存在错误、路径安全检查）
- [x] 5.2 实现 `WriteFileTool`（自动创建父目录、覆盖写入、路径安全检查）
- [x] 5.3 实现 `EditFileTool`（精确字符串替换、匹配不唯一/未找到错误）
- [x] 5.4 实现 `ListDirTool`（目录列表、类型标识、空目录/不存在处理）
- [x] 5.5 所有文件系统工具接收 `workspace` 参数，实现工作区路径限制
- [x] 5.6 编写 `tests/test_tool_filesystem.py`：验证四个工具的各种场景

## 6. Shell 执行工具实现

- [x] 6.1 创建 `src/open_agent/tools/shell.py`：实现 `ExecTool`（asyncio.create_subprocess_shell 异步执行、超时控制、工作目录限制）
- [x] 6.2 实现输出截断（max_output_chars 默认 10000）
- [x] 6.3 集成 SafetyManager 命令安全检查（check_command 在 execute 前调用）
- [x] 6.4 编写 `tests/test_tool_shell.py`：验证成功执行、超时、非零退出码、安全阻止

## 7. Web 工具实现

- [x] 7.1 创建 `src/open_agent/tools/web.py`：实现 `WebSearchTool`（Brave Search API、结果格式化、API Key 缺失处理）
- [x] 7.2 实现 `WebFetchTool`（httpx.AsyncClient、内容提取、截断、协议限制）
- [x] 7.3 集成 SafetyManager SSRF 防护（check_url 在 execute 前调用）
- [x] 7.4 添加 `httpx` 到项目依赖
- [x] 7.5 编写 `tests/test_tool_web.py`：验证搜索、抓取、SSRF 阻止、截断

## 8. Todo 工具升级

- [x] 8.1 重构 `src/open_agent/tools/todo.py`：`TodoTool` 继承 Tool ABC，包装原有 `TodoManager` 和 `todo_handler` 逻辑
- [x] 8.2 保留 TodoManager 的整份重写模式、in_progress 唯一性约束、render() 渲染
- [x] 8.3 TodoTool 的 execute() 通过依赖注入接收 TodoManager（构造函数参数）
- [x] 8.4 更新相关测试：`tests/test_harness.py` 中 todo 相关测试适配新接口

## 9. Runtime 集成与自动发现

- [x] 9.1 在 `AgentRuntime.on_start()` 中调用 `scan_builtin_tools()` 注册所有内置工具
- [x] 9.2 实现条件注册：根据 config 决定是否注册 exec 工具（exec_config.enable）
- [x] 9.3 更新 `PromptBuilder` / `ToolListSegment`：消除工具 schema 双重注入（ToolListSegment 改为轻量引用或移除）
- [x] 9.4 更新 CLI `agent tool list` 命令：从 ToolRegistry 读取实际注册的工具列表
- [x] 9.5 清理 `src/open_agent/base.py` 中废弃的 `ToolExecutor` ABC

## 10. 清理与迁移

- [x] 10.1 在 `src/open_agent/decorators.py` 的 `@tool_schema` 中添加 DeprecationWarning
- [x] 10.2 更新 `src/open_agent/mcp_integration.py`：MCP 工具注册改用 `FunctionTool` 适配器包装
- [x] 10.3 更新 `tests/test_mcp.py`：适配新的 FunctionTool 适配器
- [x] 10.4 更新 `tests/test_harness.py` 和 `tests/test_agent.py`：适配 Tool ABC + ToolRegistry v2 接口
- [x] 10.5 更新 `config.yaml`：添加 tools 相关配置节（exec enable、web search api key、max_tool_result_tokens）
