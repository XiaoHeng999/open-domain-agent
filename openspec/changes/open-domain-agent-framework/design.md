## Context

本项目从零构建一个开放域 Agent 框架。当前没有任何已有代码或系统，所有模块均为全新设计。目标用户是需要硬核 Agent 工程能力的开发者和研究人员，他们需要理解并实践 Agent Loop Design、Tool Design、Context Engineering 和 Eval Pipeline。

设计哲学为 **Harness Engineering**：每个组件必须可观测、可调试、可配置、可回滚。框架不追求 "开箱即用" 的便捷性，而是追求 "每一步都可见可控" 的工程严谨性。

技术栈：Python 3.11+，异步优先（asyncio），类型注解全覆盖。CLI 使用 **Typer + Rich**。配置层使用 **Pydantic v2**（配置校验 + 序列化）。核心数据结构使用 **dataclass**。LLM 后端抽象化，支持 OpenAI / Anthropic / DeepSeek / 本地模型。解耦 Config / Model / Provider / Tool / MCP / Prompt / Memory 等。

设计模式：
- **Registry Pattern（注册表模式）**: 工具注册表、技能注册表、恢复策略注册表——支持运行时动态增删查改
- **Factory Pattern（工厂模式）**: Provider 工厂、Memory 工厂、Agent 工厂——根据配置动态创建实例
- **Abstract Base Class + 继承**: 所有核心组件定义 ABC（IntentRecognizer、MemoryManager、ToolExecutor 等），具体实现继承基类
- **Decorator 模式**: @tool_schema 装饰器自动从函数签名生成 JSON Schema，@lifecycle hooks 生命周期管理

整体架构：

```
                ┌────────────────────┐
                │   User Request     │
                └─────────┬──────────┘
                          ↓
            ┌──────────────────────────┐
            │ D3 Routing Layer         │
            │ - complexity judge       │
            │ - domain router          │
            │ - intent parser          │
            └─────────┬───────────────┘
                          ↓
            ┌──────────────────────────┐
            │ D1 Agent Loop (ReAct)    │
            │ - plan step (optional)   │
            │ - tool calling           │
            │ - state update           │
            └─────────┬───────────────┘
                          ↓
        ┌────────────────────────────────┐
        │ Execution Subsystems          │
        │ - D6 Tool Error Recovery      │
        │ - D2 Memory                   │
        │ - D5 Checkpoint               │
        └─────────┬─────────────────────┘
                          ↓
            ┌──────────────────────────┐
            │ D7 Trace System          │
            │ (贯穿所有模块)             │
            └─────────┬───────────────┘
                          ↓
            ┌──────────────────────────┐
            │ D4 Scenario Eval (offline)│
            └──────────────────────────┘
```

## Goals / Non-Goals

**Goals:**
- 构建基于 ReAct 的 Agent 执行循环，前置意图识别与路由，后接工具执行与记忆管理
- 每个模块独立可测，通过标准化接口交互，解耦 Config / Model / Provider / Tool / MCP等
- 提供 Scenario-Based 评测管线（scenario definition + trace replay + assertion-based eval）
- 所有 Agent 行为可追溯——trace 贯穿路由决策、工具调用、记忆读写
- Long-horizon 任务支持 step-level checkpoint 和 resume
- 路由层支持 complexity judge + domain router，使用轻量 LLM（DeepSeek）或 rule+embedding
- 框架本身培养 Agent Loop Design、Tool Design、Context Engineering、Eval Pipeline 能力

**Non-Goals:**
- 不做通用聊天机器人 UI
- 不做 LLM 训练/微调
- 不做多语言 SDK（仅 Python）
- 不做生产级部署编排（Kubernetes 等）
- 不做完整的 DAG workflow system——long-horizon 用 optional planning step + step-level checkpoint，不做 DAG 调度
- 不做 OpenTelemetry 完整基础设施（Jaeger/Collector/Distributed Tracing），只做 OTel-like data model
- 不做 embedding-based capability routing——路由基于规则 + 轻量 LLM 分类
- 不做 LLM every-step eval——只在 offline scenario eval 中使用 LLM-as-Judge
- 不做 Semantic KB / RAG 的完整实现——本期保留接口，后续迭代

## Decisions

### D1: Agent Runtime 基于 ReAct 循环 + Optional Planning

**选择**: ReAct（Reasoning + Acting）循环作为核心 Agent Runtime，复杂任务可选加 planning step
**替代方案**: Plan-then-Execute 全局规划、Reflexion、纯 Function Calling、DAG 调度
**理由**: ReAct 提供最清晰的 thought → action → observation → reflection 结构，每个步骤有明确输入输出。对于复杂任务，在进入 ReAct 循环前加一个 optional planning step 生成步骤列表，但不需要完整的 DAG——planning step 输出的是有序步骤，ReAct 循环逐步执行，每步都有 checkpoint。

Agent Runtime 三个核心职责：
- **ReAct Loop**: thought → action (tool call) → observation → reflection
- **Tool Execution**: 通过 MCP 调用工具，结果返回 observation
- **State Update**: 更新 memory、checkpoint、trace

```
Routing Result → [Planning Step (optional)] → ReAct Loop {
    Thought → Action → Tool Execution → Observation → Reflection
    → Checkpoint (step-level)
} → Response
```

### D2: 记忆系统——Working Memory + Episodic Summary + User Profile State

**选择**: 三层记忆，但聚焦于 Agent 执行所需的即时上下文管理
**替代方案**: 单一长上下文、纯向量检索、MemGPT 式分页
**理由**:

三层记忆架构：
- **Working Memory**: 当前 context window 的完整对话上下文，受 token 限制，自动压缩
- **Episodic Summary Store**: 历史对话的结构化摘要（意图、结果、关键决策点）
- **User Profile State**: 长期用户状态画像（偏好、习惯、历史模式）

写入策略（三种触发时机）：
- **After Task**: 任务完成时写入 episodic summary 和 user profile 更新
- **After Reflection**: ReAct reflection 阶段发现有价值的洞察时写入
- **After Checkpoint**: checkpoint 持久化时同步刷新记忆

失败驱动记忆强化：记录 tool error pattern、hallucination pattern、用户纠正，形成 "avoidance hints"。

Semantic KB / RAG 保留接口定义，本期不实现完整功能。

### D3: 意图识别 + 分层路由

**选择**: 三阶段路由——Complexity Judge → Domain Router → Intent Parser
**替代方案**: 单阶段端到端意图识别、纯 prompt-based 提取
**理由**: 分层路由允许在早期阶段用极低成本（rule/embedding）过滤简单请求，只在必要时调用 LLM。

三阶段设计：
1. **Complexity Judge**: 判断任务是简单还是复杂，输出 complexity (simple/complex) + confidence。简单任务直接进入 ReAct 循环，复杂任务先经过 planning step。实现方式：rule-based（关键词/长度）+ 可选轻量 LLM（DeepSeek）
2. **Domain Router**: 将请求路由到对应 domain agent（coding / search / web / general 等）。每个 domain 是同一个 Agent 类但不同 system prompt，保证上下文隔离不污染。实现方式：轻量 LLM 分类或 rule + embedding 相似度
3. **Intent Parser**: 在 domain 内提取结构化 intent + slots。实现方式：轻量 LLM 结构化输出

```
Input → [Complexity Judge] → [Domain Router] → [Intent Parser] → Structured Intent → Agent
```

### D4: Scenario-Based Evaluation（外循环 / Offline）

**选择**: 基于 Scenario 的评测框架——scenario definition + trace replay + assertion-based eval
**替代方案**: 纯输出对比（BLEU/ROUGE）、LLM every-step eval、人工评估
**理由**: Agent 质量不能只看最终输出。Scenario-Based Eval 允许在执行过程的每个步骤设定断言（工具调用参数、中间状态、最终输出），是最适合 Agent 的评测方式。只在最终输出评估中使用 LLM-as-Judge，不做 LLM every-step eval（成本和延迟不可接受）。

核心组件：
- **Scenario Definition**: 定义输入 + 预期 tool call 序列 + 预期输出 + per-step assertions
- **Trace Replay**: 重放执行 trace，逐 step 对比实际 vs 预期
- **Assertion-Based Eval**: 每个 step 可以设多个 assertion（tool_called_with、output_matches、state_equals 等）
- **Metrics**: intent accuracy、tool call success rate、task completion rate、avg turns

### D5: Step-Level Checkpoint + Resume

**选择**: 在 ReAct 循环的每一步保存 checkpoint，支持从任意 step resume，不做 DAG
**替代方案**: DAG 级别 checkpoint、无 checkpoint 纯重试、全局快照
**理由**: ReAct 循环本身就是线性的步骤序列（step 1, 2, 3...），每步保存 checkpoint 足以支持 partial recovery。DAG 调度增加了大量工程复杂度但不适用于 ReAct 循环——ReAct 的下一步依赖上一步的 observation，无法真正并行。

Checkpoint 包含：
- **Step-Level State Snapshot**: 当前 step number、累积 context、tool call history、memory snapshot
- **Resume Capability**: 从指定 step 重新开始执行，恢复 context 和 memory
- **Idempotent Tasks**: 同一 step 的 checkpoint 可以安全重入，不会重复执行副作用

状态持久化：checkpoint 存储到本地文件系统（JSON/SQLite），可扩展到外部存储。

### D6: 工具错误恢复——分类 + 确定性策略

**选择**: 四类错误 + 确定性恢复策略链
**替代方案**: 统一重试、依赖 LLM 判断恢复策略、人工介入
**理由**: 确定性策略让错误恢复可预测、可调试、可测试。每种错误类型有明确的处理流程，不依赖 LLM "自由发挥"。

四类错误：
1. **ParameterError**: 参数格式/类型/缺失 → 自动修正参数 → 重试
2. **RetrievalError**: 检索结果不全或召回差 → 扩展查询（同义词/放宽过滤/降级缓存）→ 重试
3. **ServiceError**: 服务不可用或超时 → 指数退避重试 → fallback 工具
4. **ParseError**: 返回结果无法解析 → 切换输出格式 → LLM 辅助解析

```
Tool Call → Error?
  → Classify Error (4 types)
  → Apply Deterministic Recovery Policy
  → Retry (max N times)
  → Fallback or Report
```

### D7: Trace System——OTel-like Data Model

**选择**: 自建 OTel-like trace data model，不做完整 OpenTelemetry 基础设施
**替代方案**: 完整 OpenTelemetry 集成（Jaeger/Collector）、自定义日志格式
**理由**: 只需要 trace_id + span + structured logging 的数据模型，不需要分布式追踪的完整基础设施。自建模型更轻量，更适合教学和调试。

Trace 贯穿所有模块：
- **Every routing decision**: complexity judge 结果、domain 路由选择、intent 解析结果
- **Every tool call**: 工具名、参数、返回值、耗时、错误信息
- **Every memory read/write**: 操作类型、目标层、内容摘要、耗时

数据模型：
- `Trace`: trace_id + metadata + spans[]
- `Span`: span_id + parent_id + operation + attributes + status + timestamp + duration
- 所有日志 structured JSON，包含 trace_id 关联

### D8: MCP 集成——Python MCP SDK + Multi-Transport + Sandbox

**选择**: 使用 Python 版 MCP 包（`mcp`），支持 SSE / HTTP / stdio 三种 transport，集成到 Tool 层
**替代方案**: 自定义工具协议、仅 stdio transport
**理由**: Python MCP SDK 是官方维护的，支持多种 transport。SSE 和 HTTP transport 支持远程工具服务，stdio 支持本地进程工具。sandbox 执行环境确保工具调用的安全性。

工具 Schema 要求：每个工具必须定义完整的 JSON Schema（参数名、类型、描述、默认值），通过 MCP 协议注册。Schema 定义与工具实现分离，便于文档生成和验证。

### D9: 解耦架构——Config / Model / Provider / Tool / MCP

**选择**: 每个关注点独立模块，通过标准接口交互，Pydantic 配置 + YAML 驱动
**替代方案**: 大一统类、全局单例、硬编码配置
**理由**: 解耦是 Harness Engineering 的基础。Config 用 Pydantic BaseModel 定义配置 schema（自带校验和序列化），Model 定义 LLM 调用接口（ABC），Provider 通过 Factory 创建（OpenAI/Anthropic/DeepSeek），Tool 定义工具接口，MCP 实现工具协议。

```
Config (Pydantic + YAML) → Model (ABC) → ProviderFactory → Provider (OpenAI/Anthropic/DeepSeek/Local)
                        → ToolRegistry (dynamic) → MCP (stdio/SSE/HTTP transport)
                        → MemoryFactory → Memory (ABC) → Working/Episodic/UserProfile
                        → SkillRegistry (dynamic, lazy-load) → Skills (markdown+yaml)
```

### D10: CLI 与交互层——Typer + Rich

**选择**: 使用 Typer 构建 CLI 接口，Rich 提供终端格式化输出（表格、进度条、trace 展示）
**替代方案**: Click、argparse、纯 Python REPL
**理由**: Typer 基于 Click 但提供更好的类型提示支持和自动帮助文档生成。Rich 提供终端富文本输出，适合展示 trace、评测报告、状态表格。CLI 是开发者与 Agent 交互的主要入口。

主要 CLI 命令：
- `agent run "task"` — 执行单次任务
- `agent chat` — 进入多轮对话模式
- `agent eval --suite <name>` — 运行评测套件
- `agent trace <trace_id>` — 查看执行 trace
- `agent tool list` — 列出已注册工具
- `agent skill list` — 列出可用技能

### D11: 技能系统（Skills）——Markdown + YAML 元数据 + 按需加载

**选择**: 技能以 Markdown 文件 + YAML frontmatter 元数据定义，支持内置技能和工作区自定义技能，按需加载到 prompt
**替代方案**: 硬编码技能、纯 Python 类技能、数据库存储
**理由**: Markdown + YAML 是最直观的技能定义方式——技能本质上就是 "结构化的 prompt + 工具使用指南"。按需加载避免 context 膨胀。开发者可以在工作区 `.skills/` 目录下创建自定义技能，框架自动发现。

技能文件格式：
```markdown
---
name: code-review
description: 代码审查技能，支持多语言
domain: coding
tools: [file_read, search, git_diff]
trigger: "审查代码" | "code review" | "review"
---

## 指令
你是一个代码审查专家...

## 工具使用指南
1. 先使用 git_diff 查看变更...
```

技能生命周期：
- **Discovery**: 启动时扫描内置技能目录 + 工作区 `.skills/` 目录
- **Registration**: 解析 YAML 元数据，注册到 SkillRegistry（只加载元数据，不加载内容）
- **Matching**: 路由阶段根据 domain 和 trigger 匹配技能
- **Loading**: 匹配到技能时才加载 Markdown 内容，注入 Agent 的 system prompt
- **Cleanup**: 任务完成后从 context 中移除技能内容

### D12: 安全防护——命令安全 + SSRF 保护 + 工作区限制

**选择**: 分层安全防护，在工具执行前进行安全检查
**替代方案**: 信任所有工具调用、依赖 sandbox 隔离
**理由**: Sandbox 提供底层隔离，但上层也需要命令级安全检查作为深度防御。

三层安全防护：

1. **命令安全（Command Safety）**:
   - 黑名单阻止破坏性命令：`rm -rf /`、`mkfs`、`dd if=/dev/zero`、fork bomb（`:(){ :|:& };:`）、`chmod 777 /` 等
   - 正则匹配命令模式，阻止危险操作变体
   - 白名单机制：允许特定安全命令自动执行

2. **SSRF 保护**:
   - 阻止内网地址：`127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`
   - 阻止私有域名：`localhost`、`*.local`、`*.internal`
   - 阻止云元数据端点：`169.254.169.254`
   - DNS 重绑定防护：解析后再次检查 IP

3. **工作区限制（Workspace Restriction）**:
   - 文件操作限制在配置的工作区目录内
   - 路径遍历防护：阻止 `../` 越界访问
   - 敏感文件保护：`.env`、`credentials`、`*.key` 等文件只读或完全阻止

### D13: Human-in-the-Loop（HITL）——分层审批

**选择**: 基于操作类型的分层审批机制：Read 自动通过 → Write 需人类确认 → 危险操作直接阻止
**替代方案**: 全部自动执行、全部需确认、纯 sandbox 隔离
**理由**: 全自动在 Agent 开发阶段风险过高，全部确认则效率太低。分层审批在安全和效率间取得平衡——读操作无副作用自动通过，写操作需确认，危险操作直接拒绝。

三层审批：
- **Read（自动通过）**: 文件读取、搜索查询、状态查询、无害的 API GET 请求
- **Write（需人类确认）**: 文件写入/修改、API POST/PUT 请求、工具安装、配置变更
  - CLI 模式下通过 Rich 交互式确认（`[y/N]`）
  - 显示操作摘要和影响范围，帮助人类快速决策
- **Dangerous（直接阻止）**: 删除文件、系统命令、网络服务操作
  - 不经过确认，直接拒绝并返回错误
  - 记录拒绝原因到 trace

HITL 实现：通过 ToolExecutor 中间层，在工具调用前检查操作类型和审批策略。支持配置化——开发者可以调整哪些操作属于哪一层。

### D14: Sandbox-as-Tools + Daytona

**选择**: 使用 Daytona 作为 sandbox 执行环境，以 "sandbox as tools" 方式集成——sandbox 本身是一组特殊工具
**替代方案**: Docker 直接管理、无 sandbox、自建进程隔离
**理由**: Daytona 提供完整的开发环境 sandbox（文件系统、进程、网络），API 友好，支持快照和恢复。"sandbox as tools" 意味着文件操作、命令执行等都通过 sandbox 工具完成，Agent 不直接接触宿主机。

Sandbox 工具集：
- `sandbox_exec` — 在 sandbox 中执行命令
- `sandbox_read_file` — 读取 sandbox 中的文件
- `sandbox_write_file` — 写入 sandbox 中的文件
- `sandbox_snapshot` — 创建 sandbox 快照
- `sandbox_restore` — 恢复到指定快照

备选方案：若 Daytona 不适用，可降级到 Docker-based sandbox（通过 Docker SDK）或 subprocess sandbox（最小隔离）。

## Risks / Trade-offs

- **[LLM 调用延迟]** → 三阶段路由增加延迟。缓解：complexity judge 用 rule-based 快速过滤；domain router 可用 embedding 预计算；只在必要时调用 LLM。
- **[记忆一致性]** → 三层记忆之间可能出现不一致。缓解：写入策略明确（after task / after reflection / after checkpoint），读取时做一致性检查。
- **[MCP 生态成熟度]** → MCP 协议仍在演进中。缓解：抽象 MCP transport 层，协议变更只需修改适配器。
- **[Planning step 与 ReAct 的衔接]** → planning step 生成的计划可能与 ReAct 实际执行偏离。缓解：plan 作为 guidance 而非 constraint，ReAct 可以偏离计划；checkpoint 记录偏离情况。
- **[Checkpoint 存储开销]** → 每 step 保存 checkpoint 可能占用大量存储。缓解：可配置 checkpoint 粒度（每步 / 每 N 步 / 仅关键步骤）；旧 checkpoint 可清理。
- **[确定性恢复策略的覆盖度]** → 四类错误可能无法覆盖所有情况。缓解：提供 "report to agent" 兜底策略；支持自定义策略注册。
- **[框架学习曲线]** → Harness Engineering 要求理解每个组件内部机制。缓解：每个模块一个文件，渐进式教程，从最简配置开始。
- **[Sandbox 安全性]** → 工具 sandbox 可能限制部分功能。缓解：sandbox 可配置（strict/permissive/off）；生产环境建议 strict。
- **[Daytona 依赖]** → Daytona 服务需要额外部署和运维。缓解：支持 Docker fallback；sandbox 层完全解耦，可通过 Factory 切换实现。
- **[HITL 效率]** → 频繁的写操作确认可能打断工作流。缓解：支持 session-level 信任提升（确认 N 次后自动升级为信任）；支持白名单路径。
- **[技能匹配精度]** → 技能 trigger 匹配可能误触或遗漏。缓解：结合 domain + trigger 双重匹配；支持 fuzzy matching。
- **[命令安全绕过]** → 攻击者可能构造变体绕过黑名单。缓解：正则匹配覆盖常见变体；白名单模式作为可选严格模式；sandbox 提供底层兜底。
