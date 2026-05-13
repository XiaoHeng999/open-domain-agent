## Context

当前 Agent 的工具集由 `scan_builtin_tools()` 注册，涵盖文件操作、shell 执行、Web 搜索/抓取和 todo 管理。沙箱（`sandbox/`）和 MCP（`mcp_integration.py`）作为内部基础设施存在，但未暴露为 Agent 可调用的工具。subagent 系统有 explore/plan/general 三个预设，缺少面向代码审查和编写的专用预设。

项目遵循以下架构约定：
- 每个 Tool 继承 `Tool` ABC（`tools/base.py`），实现 `name`/`description`/`parameters`/`execute()`
- 工具注册通过 `ToolRegistry.register()` 完成，`scan_builtin_tools()` 负责自动注册
- 沙箱有独立模块（`sandbox/factory.py`），提供 `exec`/`read_file`/`write_file`/`snapshot`/`restore` 接口
- MCP 有 `MCPServerManager` 管理服务端生命周期和工具注册
- subagent 预设在 `subagent/presets.py` 中以字典形式定义

## Goals / Non-Goals

**Goals:**
- 为 Agent 提供 4 个新工具（self、search、sandbox_control、mcp_client），扩展 Agent 的自省、代码搜索、隔离执行和 MCP 连接能力
- 新增 code-reviewer 和 code-writer 两个专用 subagent 预设，替代 general 用于代码相关任务
- 保持模块解耦：工具定义在 `tools/`，沙箱核心逻辑复用 `sandbox/`，MCP 核心逻辑复用 `mcp_integration.py`
- 所有新工具遵循 Tool ABC，通过 `scan_builtin_tools()` 自动注册

**Non-Goals:**
- 不修改 Tool ABC 基类接口
- 不修改 sandbox 核心模块的内部实现
- 不修改 mcp_integration.py 的传输层协议
- 不移除 general 预设（保持向后兼容）
- 不新增外部 Python 包依赖（search 工具通过 subprocess 调用 ripgrep）

## Decisions

### 1. `self` 工具 — 注入 ReActLoop 引用

**决定**：`SelfTool` 通过构造函数接收 `ReActLoop` 和 `AgentRuntime` 的弱引用，支持查看状态和修改运行参数。

**理由**：ReActLoop 已维护 `_staleness_rounds`、`_max_iterations` 等运行时状态。通过弱引用注入可避免循环引用，同时保持工具的无状态性。

**替代方案**：
- 使用全局单例 — 违反多实例设计，测试不友好
- 通过 ToolRegistry 中间件传递 — 过度复杂

### 2. `search` 工具 — subprocess 调用 ripgrep

**决定**：`SearchTool` 提供两个 action（grep/glob），通过 `asyncio.create_subprocess_exec` 调用 `rg` 命令。

**理由**：项目已有 subprocess 执行模式（ExecTool），无需引入 Python 绑定。ripgrep 是性能最优的代码搜索工具，大多数开发环境已安装。

**替代方案**：
- 使用 Python `re` 模块自实现 — 性能差，不支持 .gitignore
- 安装 `pygrep` Python 包 — 额外依赖，不如 rg 性能好

### 3. `sandbox_control` 工具 — 薄封装层

**决定**：`SandboxControlTool` 作为 `tools/sandbox_control.py` 中的薄封装，委托核心操作到现有 `sandbox/factory.py` 创建的沙箱实例。沙箱实例由 runtime 注入。

**理由**：沙箱生命周期管理（创建、销毁）属于 runtime 职责。工具层仅暴露 Agent 可调用的操作接口。这保持了 sandbox 模块的独立性，同时让工具层保持轻量。

**目录划分**：
- `sandbox/` — 沙箱后端实现（Docker、Daytona、Subprocess）、工厂类
- `tools/sandbox_control.py` — 仅包含 `SandboxControlTool` 类，通过注入的 sandbox 实例调用

### 4. `mcp_client` 工具 — 复用 MCPServerManager

**决定**：`MCPClientTool` 封装 `MCPServerManager`，支持运行时动态连接新 MCP Server。工具接收 server_id、command/url 参数，调用 `MCPServerManager.register_server()` + `start_server()`。

**理由**：`MCPServerManager` 已实现完整的生命周期管理、工具发现和注册。工具层只需暴露"连接一个新 server"的操作。

**安全**：MCPClientTool 需要权限检查（safety_checks: ["command"]），防止任意命令注入。

### 5. subagent 预设 — code-reviewer 和 code-writer

**决定**：在 `subagent/presets.py` 中新增两个预设，遵循现有的 `SubagentPreset` 结构。

**code-reviewer**：
- 只读工具集：`read_file`、`list_dir`、`search`、`web_search`、`web_fetch`
- system_prompt：强调代码质量、安全性、性能审查维度
- max_turns: 15

**code-writer**：
- 写入工具集：`read_file`、`write_file`、`edit_file`、`list_dir`、`search`、`exec`
- system_prompt：强调代码规范、测试、最小改动原则
- max_turns: 20

**理由**：专用预设比 general 更精准地控制工具权限和 prompt 指导，提高任务委派质量。

## Risks / Trade-offs

- **[search 工具依赖 ripgrep]** → 文档说明安装要求，工具 execute() 中检测 rg 是否可用，不可用时返回友好错误信息
- **[self 工具暴露运行时修改能力]** → 通过 safety_checks 限制，仅允许修改白名单参数（max_iterations 等）
- **[sandbox_control 工具可能被滥用执行危险命令]** → 复用现有 sandbox 隔离机制，由 sandbox 后端负责安全
- **[mcp_client 工具允许运行时连接外部服务]** → 安全检查 + 权限系统控制，需要用户授权
- **[新增 subagent 预设增加 presets.py 维护成本]** → 预设是纯声明式定义，代码量小，且用户可通过 config 覆盖
