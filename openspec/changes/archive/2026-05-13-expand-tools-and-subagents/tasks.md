## 1. Self 工具实现

- [x] 1.1 创建 `src/open_agent/tools/self.py`，实现 `SelfTool` 类继承 Tool ABC，支持 `action` 参数（status / get_config / set_config）
- [x] 1.2 实现 `action="status"` 逻辑：通过弱引用读取 ReActLoop 当前步骤数、已用工具、对话轮次等状态
- [x] 1.3 实现 `action="get_config"` / `action="set_config"` 逻辑：白名单参数（max_iterations、staleness_rounds）的读取与修改
- [x] 1.4 为 SelfTool 编写单元测试，覆盖 status/get_config/set_config 及白名单拒绝场景

## 2. Search 工具实现

- [x] 2.1 创建 `src/open_agent/tools/search.py`，实现 `SearchTool` 类继承 Tool ABC，支持 `action` 参数（grep / glob）
- [x] 2.2 实现 `action="grep"` 逻辑：通过 asyncio.create_subprocess_exec 调用 rg，支持 pattern、path、file_type、max_results 参数
- [x] 2.3 实现 `action="glob"` 逻辑：使用 pathlib 实现文件模式匹配，支持 pattern、path 参数
- [x] 2.4 实现 ripgrep 不可用时的降级错误提示
- [x] 2.5 为 SearchTool 编写单元测试，覆盖 grep/glob 基本场景和边界情况

## 3. Sandbox Control 工具实现

- [x] 3.1 创建 `src/open_agent/tools/sandbox_control.py`，实现 `SandboxControlTool` 类继承 Tool ABC，通过构造函数注入 sandbox 实例
- [x] 3.2 实现 `action="start"` / `action="exec"` / `action="snapshot"` / `action="restore"` 各操作，委托到 sandbox 实例方法
- [x] 3.3 为 SandboxControlTool 编写单元测试，使用 mock sandbox 实例验证各 action

## 4. MCP Client 工具实现

- [x] 4.1 创建 `src/open_agent/tools/mcp_client.py`，实现 `MCPClientTool` 类继承 Tool ABC，通过构造函数注入 MCPServerManager 实例
- [x] 4.2 实现 `action="connect"` 逻辑：创建 ServerConfig 并调用 MCPServerManager 注册/启动服务器
- [x] 4.3 实现 `action="disconnect"` 逻辑：停止服务器并从 ToolRegistry 移除其工具
- [x] 4.4 实现 `action="list"` 逻辑：返回已连接服务器列表及工具数量
- [x] 4.5 为 MCPClientTool 编写单元测试，使用 mock MCPServerManager 验证各 action

## 5. Subagent 专用预设实现

- [x] 5.1 在 `src/open_agent/subagent/presets.py` 中新增 `code-reviewer` 预设：只读工具集 + 审查维度 system prompt + max_turns=15
- [x] 5.2 在 `src/open_agent/subagent/presets.py` 中新增 `code-writer` 预设：写入工具集 + 编写导向 system prompt + max_turns=20
- [x] 5.3 更新 presets 测试，覆盖两个新预设的字段值正确性

## 6. 注册集成与 Runtime 编排

- [x] 6.1 在 `src/open_agent/registry.py` 的 `scan_builtin_tools()` 中注册 SearchTool
- [x] 6.2 在 `src/open_agent/runtime.py` 的 `on_start()` 中创建并注册 SelfTool（注入 ReActLoop 引用）
- [x] 6.3 在 `src/open_agent/runtime.py` 的 `on_start()` 中创建并注册 SandboxControlTool（注入 sandbox 实例）
- [x] 6.4 在 `src/open_agent/runtime.py` 的 `on_start()` 中创建并注册 MCPClientTool（注入 MCPServerManager 实例，仅在 MCP 配置存在时）
- [x] 6.5 验证所有新工具在 `get_definitions()` 中正确输出 Anthropic tool_use schema
- [x] 6.6 集成测试：端到端验证 Agent 可通过 ReActLoop 调用所有新工具
