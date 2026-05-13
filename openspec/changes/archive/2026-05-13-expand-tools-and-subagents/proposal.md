## Why

Agent 当前工具集缺少几项核心能力：无法进行运行时自省与动态配置调整（`self`），缺少代码级别的搜索能力（grep/glob），沙箱仅作为内部组件存在而未暴露为 Agent 可调用的工具（`sandbox`），MCP 客户端尚未作为原生工具注册。同时，subagent 仅有一个通用的 `general` 预设，缺乏面向代码审查和代码编写场景的专用预设，导致任务委派不够精准。

## What Changes

- 新增 `self` 工具：运行时状态检查与配置热更新（查看当前步骤数、已用工具、对话轮次、修改运行参数等）
- 新增 `search` 工具：基于 ripgrep 的代码搜索（grep）和文件模式匹配（glob），无需通过 shell 执行
- 新增 `sandbox` 工具：将现有沙箱基础设施暴露为 Agent 可调用的工具（启动/停止沙箱、在沙箱中执行命令、快照/恢复）
- 新增 `mcp` 工具：MCP 客户端工具，连接 MCP Server 并将其工具包装为原生工具动态注册到 ToolRegistry
- 新增 `code-reviewer` subagent 预设：专注于代码审查，只读访问，配备特定的审查 system prompt
- 新增 `code-writer` subagent 预设：专注于代码编写，拥有文件编辑和执行权限，配备编写导向的 system prompt
- 保留 `general` 预设不变，确保向后兼容

## Capabilities

### New Capabilities

- `tool-self-inspection`: 运行时状态自省工具，支持查看和动态修改 agent loop 运行参数
- `tool-code-search`: 基于 ripgrep 的 grep 和 glob 代码搜索工具
- `tool-sandbox-control`: 沙箱生命周期管理工具（start/stop/exec/snapshot/restore）
- `tool-mcp-client`: MCP 客户端工具，动态连接 MCP Server 并注册其工具
- `subagent-specialized-presets`: 新增 code-reviewer 和 code-writer 专用 subagent 预设

### Modified Capabilities

- `subagent-presets`: 新增两个专用预设（code-reviewer、code-writer），现有预设不变

## Impact

- **新增文件**：`tools/self.py`、`tools/search.py`、`tools/sandbox_control.py`、`tools/mcp_client.py`
- **修改文件**：`subagent/presets.py`（新增预设）、`registry.py`（注册新工具）、`runtime.py`（工具初始化编排）
- **依赖**：`ripgrep`（search 工具）、现有 sandbox 和 mcp_integration 模块
- **向后兼容**：所有变更均为新增，不破坏现有 API
