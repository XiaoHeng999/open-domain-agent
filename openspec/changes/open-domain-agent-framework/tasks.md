## 1. Harness Infrastructure 基础（所有模块依赖）

- [ ] 1.1 初始化项目结构：`src/open_agent/` 包目录，pyproject.toml（Python 3.11+，依赖：typer、rich、pydantic、mcp），每个功能一个文件
- [ ] 1.2 实现 Pydantic 配置层（config.py）：BaseModel 定义所有配置 schema，YAML 加载 + 环境变量覆盖 + 运行时参数注入 + Pydantic 自动校验
- [ ] 1.3 实现 ABC 基类体系（base.py）：BaseComponent(ABC) 定义生命周期钩子（on_register / on_start / on_stop / on_error）；定义 MemoryManager(ABC)、ToolExecutor(ABC)、IntentRecognizer(ABC)、Router(ABC) 等接口
- [ ] 1.4 实现 Model 接口与 ProviderFactory（model.py + provider/）：ABC 定义 LLM 调用接口，ProviderFactory 根据 config 创建 OpenAI / Anthropic / DeepSeek provider 实例
- [ ] 1.5 实现 @tool_schema 装饰器（decorators.py）：自动从函数签名 + docstring 生成 MCP 兼容 JSON Schema
- [ ] 1.6 实现 OTel-like Trace Data Model（trace.py）：Trace + Span + structured JSON logging，不做完整 OTel infra
- [ ] 1.7 实现统一错误类型层级（errors.py）：AgentError → ToolError / MemoryError / RoutingError / EvalError / DangerousOperationError / SSRFError，保留错误链
- [ ] 1.8 实现 Dynamic ToolRegistry（registry.py）：运行时 register / unregister / list / list_by_tag，Registry Pattern
- [ ] 1.9 实现回退与降级机制：FallbackChain + 降级策略
- [ ] 1.10 实现 CLI 入口（cli.py）：Typer 命令定义（run / chat / eval / trace / tool / skill），Rich 格式化输出（表格、进度条、trace 展示）
- [ ] 1.11 编写 harness-infrastructure 单元测试：配置加载校验、ABC 继承、Factory 创建、Registry 动态增删、trace 生成、CLI 命令

## 2. Security & Sandbox 安全防护与沙箱

- [ ] 2.1 实现命令安全防护（safety/command.py）：黑名单（rm -rf / mkfs / dd / fork bomb 等）+ 正则模式匹配，支持白名单模式
- [ ] 2.2 实现 SSRF 保护（safety/ssrf.py）：内网 IP 段阻止（127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16）+ 私有域名阻止 + 云元数据端点阻止 + DNS 重绑定防护
- [ ] 2.3 实现工作区路径限制（safety/workspace.py）：路径遍历防护（../）+ 敏感文件保护（.env / credentials / *.key）+ 工作区边界检查
- [ ] 2.4 实现 Human-in-the-Loop 分层审批（safety/hitl.py）：Read 自动通过 → Write 需 Rich 交互式确认 → Dangerous 直接阻止；支持 session-level 信任提升和白名单路径
- [ ] 2.5 实现安全级别配置（safety/__init__.py）：strict / permissive / off 三级，统一安全管理接口
- [ ] 2.6 实现 Sandbox-as-Tools（sandbox/daytona.py）：Daytona 集成，提供 sandbox_exec / sandbox_read_file / sandbox_write_file / sandbox_snapshot / sandbox_restore 五个工具
- [ ] 2.7 实现 Docker Sandbox fallback（sandbox/docker.py）：Daytona 不可用时降级到 Docker SDK 实现
- [ ] 2.8 实现 SandboxFactory（sandbox/factory.py）：根据配置选择 Daytona / Docker / Subprocess sandbox 实现
- [ ] 2.9 编写 security & sandbox 测试：命令阻止、SSRF 阻止、路径限制、HITL 各层级、sandbox 执行

## 3. MCP Integration 工具协议层

- [ ] 3.1 集成 Python MCP 包（`mcp`），实现 transport 抽象层：stdio / SSE / HTTP 三种 transport 统一接口
- [ ] 3.2 实现 MCP Server 生命周期管理：注册、启动、停止、健康检查，配合 BaseComponent 生命周期钩子
- [ ] 3.3 实现工具 Schema 强制定义：注册时必须提供 JSON Schema（通过 @tool_schema 装饰器自动生成），Schema 与工具实现分离
- [ ] 3.4 实现标准化工具调用接口：统一调用入口，自动处理 transport 差异，集成 ToolRegistry 动态注册
- [ ] 3.5 实现工具调用 Trace：每次调用的 input/output/latency/error 完整记录到 span
- [ ] 3.6 编写 mcp-integration 测试：多 transport 注册、Schema 校验、ToolRegistry 动态增删、@tool_schema 装饰器

## 4. 三阶段路由层（Complexity Judge → Domain Router → Intent Parser）

- [ ] 4.1 实现 Complexity Judge（routing/complexity.py）：rule-based（关键词/长度）+ 可选轻量 LLM（DeepSeek），输出 complexity + confidence
- [ ] 4.2 实现 Domain Router（routing/domain.py）：支持 coding / search / web / general 等 domain，每个 domain 对应不同 system prompt
- [ ] 4.3 实现 Domain Agent 上下文隔离：同一 Agent 类 + 不同 system prompt，各 domain context 不互相污染
- [ ] 4.4 实现 Intent Parser（routing/intent.py）：domain 内结构化 intent + slots 提取，支持槽位缺失时生成澄清问题
- [ ] 4.5 实现简单任务直通：complexity=simple 且 confidence>0.9 时跳过 planning step
- [ ] 4.6 实现路由决策 Trace：三阶段的完整决策过程记录
- [ ] 4.7 实现路由评测接口：接受测试集，输出 complexity_accuracy / domain_accuracy / intent_accuracy / slot_f1
- [ ] 4.8 编写路由层测试：简单/复杂任务、domain 路由、intent 解析、上下文隔离

## 5. Agent Runtime（ReAct Loop + Optional Planning）

- [ ] 5.1 实现 ReAct Loop 核心（agent/react.py）：thought → action (tool call) → observation → reflection 循环，基于 dataclass 定义核心数据结构
- [ ] 5.2 实现 Optional Planning Step（agent/planner.py）：Complexity Judge 判定为 complex 时生成有序步骤列表（非 DAG），作为 guidance
- [ ] 5.3 实现 Tool Execution 集成：ReAct action 通过 MCP + ToolRegistry 调用工具，集成安全检查（command safety / SSRF / HITL）
- [ ] 5.4 实现 State Update：每步更新 working memory、触发 memory 写入策略（after reflection / after checkpoint）
- [ ] 5.5 实现 Agent Loop Trace：每轮迭代的 thought/action/observation/reflection 完整记录
- [ ] 5.6 实现 Planning Deviation 检测：ReAct 偏离 plan 时在 trace 中记录
- [ ] 5.7 编写 Agent Runtime 集成测试：简单任务直通、复杂任务规划、多轮对话、偏离计划、安全检查拦截

## 6. Memory System（Working + Episodic + User Profile）

- [ ] 6.1 实现 Working Memory（memory/working.py）：当前 context window 管理，token 计数，自动压缩（保留最近 N 轮 + 早期摘要），继承 MemoryManager(ABC)
- [ ] 6.2 实现 Episodic Summary Store（memory/episodic.py）：历史对话结构化摘要（意图/结果/决策点），三种写入触发（after task / after reflection / after checkpoint）
- [ ] 6.3 实现 User Profile State（memory/profile.py）：长期用户偏好/习惯/模式，对话开始加载、对话结束更新
- [ ] 6.4 实现记忆检索增强：基于当前意图自动检索 episodic summary 和 user profile，注入 working memory
- [ ] 6.5 实现失败驱动记忆强化：记录 tool error pattern / hallucination / 用户纠正，生成 avoidance hints
- [ ] 6.6 实现记忆操作 Trace：每次读写的 memory_layer / query / results / latency 记录
- [ ] 6.7 实现 Semantic KB / RAG 接口预留（memory/semantic.py）：定义标准接口（write/query/delete），提供 in-memory stub
- [ ] 6.8 实现 MemoryFactory：根据 config 创建 memory 组件实例
- [ ] 6.9 编写 memory system 测试：压缩策略、检索增强、user profile 更新、失败记忆强化、生命周期钩子

## 7. Tool Error Recovery（四分类 + 确定性策略链）

- [ ] 7.1 实现错误分类器（recovery/classifier.py）：ParameterError / RetrievalError / ServiceError / ParseError 四类
- [ ] 7.2 实现 ParameterError 恢复：参数格式推断 + 类型转换 + 缺失参数补全 → 重试
- [ ] 7.3 实现 RetrievalError 恢复：同义词扩展 → 放宽过滤 → 降级缓存（确定性策略链）
- [ ] 7.4 实现 ServiceError 恢复：指数退避重试（最多 3 次）→ fallback 工具查找
- [ ] 7.5 实现 ParseError 恢复：切换输出格式 → LLM 辅助解析
- [ ] 7.6 实现策略链引擎（recovery/engine.py）：有序策略执行、链耗尽时 report_to_agent
- [ ] 7.7 实现自定义恢复策略注册接口：通过 Registry Pattern 注册到 RecoveryPolicyRegistry
- [ ] 7.8 实现错误恢复 Trace：错误分类 + 每次策略尝试 + 最终状态
- [ ] 7.9 编写 tool-error-recovery 测试：每类错误恢复、策略链耗尽、自定义策略、Registry 动态注册

## 8. Step-Level Checkpoint + Resume

- [ ] 8.1 实现 Step-Level Checkpoint（checkpoint/manager.py）：每步保存 step_number / context_snapshot / tool_calls_so_far / memory_state，基于 dataclass
- [ ] 8.2 实现 Checkpoint 粒度配置：支持每步 / 每 N 步 / 仅关键步骤
- [ ] 8.3 实现 Resume from Checkpoint：从指定 step 恢复 context 和 memory，重新执行
- [ ] 8.4 实现 Idempotent Task 支持：通过 idempotency key 防止副作用重复执行
- [ ] 8.5 实现状态持久化：默认 JSON 文件 / SQLite 存储，支持 CheckpointStorage(ABC) 接口扩展
- [ ] 8.6 实现 Checkpoint 触发失败记忆强化：恢复后记录失败模式到记忆
- [ ] 8.7 编写 checkpoint 测试：保存/恢复、粒度配置、idempotency、存储扩展、生命周期钩子

## 9. Skills System（技能系统）

- [ ] 9.1 实现技能文件解析（skills/parser.py）：Markdown + YAML frontmatter 解析，提取 name / description / domain / tools / trigger 元数据
- [ ] 9.2 实现内置技能扫描：扫描框架内置技能目录，自动注册到 SkillRegistry
- [ ] 9.3 实现工作区自定义技能发现：扫描 `.skills/` 目录，注册自定义技能
- [ ] 9.4 实现 Dynamic SkillRegistry（skills/registry.py）：运行时 register / unregister / list / list_by_domain，Registry Pattern
- [ ] 9.5 实现技能按需加载（Lazy Loading）：注册阶段只加载元数据，匹配时才加载 Markdown 正文，任务完成后清理
- [ ] 9.6 实现技能匹配（skills/matcher.py）：Domain + Trigger 双重匹配，集成到路由层
- [ ] 9.7 实现技能注入：匹配到的技能内容注入 Agent 的 system prompt
- [ ] 9.8 编写内置示例技能（code-review、search-analyze、web-browse 等）
- [ ] 9.9 编写 skills system 测试：文件解析、动态注册/注销、Lazy Loading、匹配逻辑、生命周期

## 10. Online Monitoring

- [ ] 10.1 实现 Trace 采集管线：所有模块的 span 采集、存储、按 trace_id 索引
- [ ] 10.2 实现异常行为检测：工具调用循环、重复错误、token 异常、执行超时
- [ ] 10.3 实现在线质量评分：task_completed(40%) + tool_efficiency(30%) + token_efficiency(20%) + no_errors(10%)
- [ ] 10.4 实现自动反馈回路：错误模式 → avoidance hint 注入 user profile；高质量 trace → eval 用例建议
- [ ] 10.5 编写 monitoring 测试：异常检测、质量评分、反馈回路

## 11. Scenario-Based Evaluation（Offline 外循环）

- [ ] 11.1 实现 Scenario Definition 数据模型（eval/scenario.py）：input + expected_tool_calls + expected_output + step_assertions，基于 dataclass
- [ ] 11.2 实现 Assertion 类型（eval/assertions.py）：tool_called_with / output_matches / output_contains / state_equals
- [ ] 11.3 实现 Trace Replay 引擎（eval/replay.py）：逐步对比实际 vs 预期，执行 assertion 检查
- [ ] 11.4 实现评测指标计算（eval/metrics.py）：Intent Accuracy / Tool Call Success Rate / Task Completion Rate / Avg Turns
- [ ] 11.5 实现 LLM-as-Judge（eval/judge.py）：仅在最终输出评估中使用，中间步骤不调用 LLM eval
- [ ] 11.6 实现评测数据集版本管理（eval/dataset.py）：版本化存储、加载、过滤、采样、版本对比
- [ ] 11.7 实现 Trace → Eval Case 转化：从执行 trace 自动生成可编辑的评测场景
- [ ] 11.8 编写 evaluation 测试：场景执行、assertion 检查、指标计算、trace 转化

## 12. 端到端集成与示例

- [ ] 12.1 实现端到端 Agent Runtime：整合所有模块，统一启动/停止/调用接口，完整生命周期管理
- [ ] 12.2 编写最小可运行示例：CLI `agent run "hello"` → 路由 → ReAct → 返回
- [ ] 12.3 编写复杂任务示例：三阶段路由 → Planning Step → ReAct + Checkpoint → Resume
- [ ] 12.4 编写工具错误恢复示例：不同错误类型的自动恢复演示
- [ ] 12.5 编写 Skills 使用示例：内置技能触发 + 工作区自定义技能
- [ ] 12.6 编写安全防护示例：HITL 交互、命令阻止、SSRF 阻止
- [ ] 12.7 编写评测套件示例：10+ 场景的端到端评测套件，Rich 输出报告
- [ ] 12.8 端到端冒烟测试：验证所有模块联合工作的完整链路
