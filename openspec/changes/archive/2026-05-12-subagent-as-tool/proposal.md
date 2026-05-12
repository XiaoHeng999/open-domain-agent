## Why

当前框架是单代理架构——一个 ReActLoop 处理所有任务。对于复杂场景（如先探索代码库再执行修改、并行搜索多个方向、将规划与执行解耦），单代理模式存在以下限制：

1. **上下文膨胀** — 所有工具调用共享同一个 transcript，复杂任务迅速耗尽上下文窗口
2. **无法并行** — 父代理必须顺序执行所有子任务，无法同时发起多个探索
3. **缺乏角色特化** — 探索、规划、代码审查等不同角色需要不同的系统提示和工具集，但当前没有机制支持
4. **级联失败风险** — 子任务的失败/重试循环会影响主对话流的 token 预算

Claude Code 的 "Agent-as-a-Tool" 模式已被行业验证为最佳实践：将子代理注册为一个 `Task` 工具，父代理像调用普通工具一样调用子代理，子代理在隔离的 transcript 中运行并返回摘要结果。

## What Changes

- **新增 `SubagentTool`** — 继承 `Tool` ABC，作为 `task` 工具注册到 `ToolRegistry`，接受 `prompt`、`subagent_type`、`run_in_background`、`max_turns` 等参数
- **新增 `SubagentManager`** — 管理子代理生命周期：预设类型注册、并发控制（max_concurrent / max_children）、级联终止、结果收集
- **新增子代理执行循环** — 复用 `ReActLoop`，但注入隔离的系统提示、限制工具集、独立迭代预算
- **新增预设子代理类型** — `explore`（只读探索）、`plan`（规划不执行）、`general`（通用）
- **扩展配置** — `AgentConfig` 新增 `subagent` 配置段，支持全局并发限制、默认超时等
- **集成到 Runtime** — `AgentRuntime` 在启动时自动注册 `SubagentTool`，子代理调用透明地通过中间件链

## Capabilities

### New Capabilities

- `subagent-tool`: 将子代理暴露为可调用工具的核心抽象——SubagentTool(Tool)、参数定义、执行流程、结果返回
- `subagent-manager`: 子代理生命周期管理——预设类型注册/查找、并发控制、后台执行与结果收集、级联终止
- `subagent-presets`: 预定义子代理类型（explore/plan/general）——角色系统提示、工具集限制、默认迭代预算

### Modified Capabilities

- `tool-registry-v2`: ToolRegistry 需支持从 SubagentManager 自动注册/卸载子代理工具
- `multi-agent-routing`: RoutingPipeline 可输出子代理类型建议，与 SubagentManager 联动

## Impact

- **新增文件**: `src/open_agent/subagent/__init__.py`, `tool.py`, `manager.py`, `types.py`, `presets.py`
- **修改文件**: `config.py`（新增 SubagentConfig）, `registry.py`（集成子代理工具注册）, `runtime.py`（启动时初始化 SubagentManager）, `config.yaml`（新增 subagent 配置段）
- **依赖**: 无新外部依赖，完全复用现有 ReActLoop、ToolRegistry、Middleware、TraceManager
- **向后兼容**: 纯增量变更，不影响现有单代理工作流
