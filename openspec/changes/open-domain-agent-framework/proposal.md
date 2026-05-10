## Why

现有的 Agent 框架（LangChain、CrewAI、AutoGen 等）大多停留在 "胶水层"——封装 API 调用和工具拼接，缺乏对 Agent 核心工程问题的系统性解决方案：意图识别的精度、工具调用的鲁棒性、长期记忆的一致性、安全防护的系统性。本项目旨在构建一个 **以 Harness Engineering 为设计哲学** 的开放域 Agent 框架，基于 ReAct 循环，前置三阶段路由（Complexity Judge → Domain Router → Intent Parser），后接工具执行与记忆管理，配合完整的 Skills 系统、安全防护（命令安全/SSRF/HITL）和 Sandbox 执行环境，培养开发者在 Agent Loop Design、Tool Design、Context Engineering 和 Eval Pipeline 四个维度上的硬核能力。

## What Changes

- **三阶段路由层**：Complexity Judge → Domain Router → Intent Parser，支持 rule-based 和轻量 LLM（DeepSeek）
- **ReAct Agent Runtime**：thought → action → observation → reflection，复杂任务可选加 planning step（有序步骤，非 DAG）
- **MCP 集成层**：Python MCP 包，支持 SSE/HTTP/stdio 三种 transport，@tool_schema 装饰器自动生成 Schema
- **三层记忆系统**：Working Memory + Episodic Summary + User Profile State，失败驱动记忆强化
- **工具错误恢复**：四类错误 + 确定性恢复策略链 + retry/fallback
- **Step-Level Checkpoint**：每步保存，支持 resume 和 idempotent task
- **OTel-like Trace System**：Trace + Span + structured JSON logging，贯穿所有模块
- **Scenario-Based Evaluation**：scenario definition + trace replay + assertion-based eval + LLM-as-Judge
- **Online Monitoring**：异常检测、质量评分、自动反馈回路
- **Skills 技能系统**：Markdown + YAML frontmatter 定义技能，内置 + 工作区自定义，Dynamic SkillRegistry，按需加载到 prompt
- **安全防护**：命令安全（rm -rf/fork bomb/mkfs 阻止）、SSRF 保护（内网/私有域名/云元数据阻止）、工作区路径限制
- **Human-in-the-Loop**：分层审批（Read 自动 → Write 确认 → Dangerous 阻止），session 信任提升
- **Sandbox-as-Tools**：Daytona sandbox + Docker fallback，sandbox 本身作为工具集
- **Harness Infrastructure**：Pydantic 配置层、ABC + 继承体系、Registry/Factory 设计模式、Typer + Rich CLI、生命周期管理

## Capabilities

### New Capabilities

- `intent-recognition`: 三阶段路由管线——Complexity Judge + Domain Router + Intent Parser，支持 rule-based 和轻量 LLM
- `mcp-integration`: Python MCP SDK 集成——stdio/SSE/HTTP transport、@tool_schema 装饰器、Dynamic ToolRegistry
- `memory-management`: 三层记忆——Working Memory + Episodic Summary + User Profile State，失败驱动记忆强化，Semantic KB 接口预留
- `agent-evaluation`: Scenario-Based 评测——scenario definition + trace replay + assertion-based eval + LLM-as-Judge
- `multi-agent-routing`: 三阶段路由——complexity judge + domain router（上下文隔离）+ intent parser
- `online-monitoring`: 在线监控——trace 采集、异常检测、质量评分、自动反馈回路
- `tool-error-recovery`: 工具错误恢复——四类错误 + 确定性策略链 + RecoveryPolicyRegistry
- `long-horizon-execution`: 长期任务——optional planning step + step-level checkpoint + resume + idempotent task
- `skills-system`: 技能系统——Markdown + YAML 元数据、内置 + 工作区自定义、Dynamic SkillRegistry、按需加载、Domain + Trigger 匹配
- `security-sandbox`: 安全防护与沙箱——命令安全、SSRF 保护、工作区限制、HITL 分层审批、Daytona/Docker sandbox
- `harness-infrastructure`: 基础设施——Pydantic 配置、ABC + 继承、Registry/Factory 模式、@tool_schema 装饰器、OTel-like trace、Typer + Rich CLI、生命周期管理

### Modified Capabilities

（无已有能力需要修改）

## Impact

- **新增代码**：11 个核心模块，每个功能一个文件，ABC 继承 + Registry/Factory 模式
- **依赖**：typer、rich、pydantic v2、mcp、LLM provider SDK（OpenAI/Anthropic/DeepSeek）、SQLite、daytona-sdk（可选）
- **不做的事**：完整 DAG workflow、OpenTelemetry 完整 infra、embedding-based routing、LLM every-step eval、Semantic KB/RAG 完整实现
- **设计约束**：Harness Engineering——可观测、可调试、可配置、可回滚；Registry + Factory 模式；ABC 继承体系；生命周期钩子
