## Why

当前框架的系统提示词（system prompt）组装逻辑分散在多个模块中（ReAct 硬编码、DomainRouter、SkillMatcher、Planner），且存在集成缺口——路由阶段的 domain system prompt 和 skill 匹配内容虽然被计算但从未实际注入到 ReAct 循环的消息构建中。需要一个统一的提示词组装流水线（Prompt Assembly Pipeline），将来自不同来源的上下文信息按优先级和语义分段组装为完整的系统提示词，同时区分稳定段（跨会话不变）和动态段（每轮会话刷新），为逻辑 agent 分层提供动态工具列表注入能力。

## What Changes

- 新增 **Prompt Assembly Pipeline** 模块，将系统提示词分为 6 个语义段按序组装：
  1. **核心身份与行为**（Core Identity）— Agent 角色定义、行为准则（稳定）
  2. **工具列表**（Tool List）— 当前可用工具的 JSON Schema 描述（动态，支持逻辑 agent 分层切换）
  3. **Skills 元信息**（Skills Metadata）— 已匹配技能的指令内容（动态，按需注入）
  4. **Memory 内容**（Memory Context）— 工作记忆、历史摘要、用户偏好（动态）
  5. **CLAUDE.md 指令链**（CLAUDE.md Directives）— 项目级指令文件加载（稳定+动态混合）
  6. **动态环境信息**（Dynamic Environment）— 时间、平台、工作目录等（每轮刷新）
- 新增 **Logical Agent Tools Layer** — 逻辑 agent 可在运行时动态修改 ToolRegistry，实现不同 agent 角色拥有不同工具集
- 扩展 **Skills 系统**，支持 Python handler 文件 + Markdown 定义文件的技能包结构
- 新增 5 个可扩展技能包骨架：`skill-creator`、`summarize`、`weather`、`github`、`wechat-mp-cn`

## Capabilities

### New Capabilities
- `prompt-pipeline`: 统一的 6 段系统提示词组装流水线，区分稳定段与动态段，支持逻辑 agent 分层的工具列表动态注入
- `skill-extensions`: 5 个新技能包（skill-creator、summarize、weather、github、wechat-mp-cn），支持 Python handler + Markdown 定义双文件结构

### Modified Capabilities
- `skills-system`: 扩展技能格式，支持 Python handler 文件（`skill_name.py`）与 Markdown 定义文件（`skill_name.md`）组成技能包，注册时同时加载工具处理函数和技能指令内容
- `multi-agent-routing`: 扩展逻辑 agent 分层，支持不同 agent 角色拥有独立的工具子集，通过 Prompt Pipeline 动态注入不同的工具列表段

## Impact

- **新增模块**: `src/open_agent/prompt/`（pipeline.py, segments.py, builder.py）
- **修改模块**: `src/open_agent/agent/react.py`（使用 Pipeline 替代硬编码 system prompt）、`src/open_agent/runtime.py`（初始化 Pipeline 并注入 ReAct）、`src/open_agent/skills/registry.py`（支持 .py handler 加载）
- **新增技能包目录**: `src/open_agent/skills/builtin/skill-creator/`、`summarize/`、`weather/`、`github/`、`wechat-mp-cn/`
- **API 变更**: ToolRegistry 新增 `snapshot()` 和 `restore()` 方法支持工具集快照；新增 `PromptPipeline` 公共 API
- **依赖**: 无新增外部依赖
