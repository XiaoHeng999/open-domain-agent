## ADDED Requirements

### Requirement: 解耦架构——Config / Model / Provider / Tool / MCP / Prompt
系统 SHALL 将 Config、Model、Provider、Tool、MCP、Prompt 完全解耦，每个关注点一个文件/模块，通过标准接口交互，Pydantic 配置驱动。

#### Scenario: 配置切换 Provider
- **WHEN** YAML 配置中 provider 从 "openai" 改为 "anthropic"
- **THEN** ProviderFactory 自动创建 Anthropic Provider，其他模块无需修改

#### Scenario: 每个功能一个文件
- **WHEN** 开发者查看项目结构
- **THEN** 每个核心功能有独立文件（config.py / model.py / provider.py / tool.py / trace.py / ...），职责清晰

### Requirement: Pydantic 配置层
系统 SHALL 使用 Pydantic v2 BaseModel 定义所有配置 schema，支持 YAML 文件加载 + 环境变量覆盖 + 运行时参数注入。Pydantic 自带类型校验和序列化。

#### Scenario: 配置自动校验
- **WHEN** YAML 中 model.temperature 设置为 "hot"（非 float）
- **THEN** Pydantic 校验失败，启动时报错并列出所有无效字段

#### Scenario: 环境变量覆盖
- **WHEN** 环境变量 OPEN_AGENT_MODEL_NAME="deepseek-chat" 已设置
- **THEN** 该值覆盖 YAML 中的 model.name 配置

### Requirement: ABC + 继承体系
系统 SHALL 为所有核心组件定义 Abstract Base Class，具体实现继承基类。基类定义生命周期钩子（on_register / on_start / on_stop / on_error）。

#### Scenario: 继承体系
- **WHEN** 开发者查看类层次
- **THEN** 结构为：AgentError(Exception) → 子类错误；BaseComponent(ABC) → MemoryManager(ABC) → WorkingMemory / EpisodicStore / UserProfileState；BaseTool(ABC) → MCPTool / SandboxTool

#### Scenario: 生命周期钩子
- **WHEN** 一个 MemoryManager 实例被注册并启动
- **THEN** 框架依次调用 on_register() → on_start()，停止时调用 on_stop()

### Requirement: Dynamic Tool Registry
系统 SHALL 实现动态工具注册表（ToolRegistry），支持运行时注册、注销、查询工具，使用 Registry Pattern。

#### Scenario: 运行时注册工具
- **WHEN** 一个新的 MCP Server 上线，提供 3 个工具
- **THEN** ToolRegistry.register(tool) 将 3 个工具加入注册表，后续 Agent 可调用

#### Scenario: 运行时注销工具
- **WHEN** 一个 MCP Server 下线
- **THEN** ToolRegistry.unregister(server_id) 移除该 Server 的所有工具

#### Scenario: 查询工具
- **WHEN** 查询 "有哪些 search 相关的工具"
- **THEN** ToolRegistry.list_by_tag("search") 返回匹配的工具列表

### Requirement: @tool_schema 装饰器
系统 SHALL 提供 @tool_schema 装饰器，自动从 Python 函数签名和 docstring 生成 MCP 兼容的 JSON Schema。

#### Scenario: 自动生成 Schema
- **WHEN** 开发者使用 @tool_schema 装饰一个带类型注解的函数
- **THEN** 框架自动提取参数名、类型、默认值、docstring 描述，生成完整 JSON Schema

### Requirement: Factory Pattern
系统 SHALL 使用 Factory Pattern 创建 Provider、Memory、Agent 等组件实例，根据配置动态选择实现类。

#### Scenario: ProviderFactory
- **WHEN** 配置中 provider.name="openai"
- **THEN** ProviderFactory.create(config) 返回 OpenAIProvider 实例

#### Scenario: MemoryFactory
- **WHEN** 配置中 memory.episodic.backend="redis"
- **THEN** MemoryFactory.create_episodic(config) 返回 RedisEpisodicStore 实例

### Requirement: OTel-like Trace Data Model
系统 SHALL 实现自建的 OTel-like trace data model（Trace + Span + structured JSON logging），不做完整 OpenTelemetry 基础设施。

#### Scenario: Trace 数据模型
- **WHEN** Agent 执行一次完整任务
- **THEN** 生成一个 Trace（含 trace_id），包含多个 Span（routing、tool_call、memory_op、agent_loop），每个 Span 有 parent_id、operation、attributes、status、timestamp

#### Scenario: Structured JSON Logging
- **WHEN** 任何模块输出日志
- **THEN** 格式为 JSON，包含 timestamp、level、module、trace_id、message，可通过 trace_id 关联完整链路

### Requirement: 回退与降级机制
系统 SHALL 支持为关键操作配置 fallback 路径。

#### Scenario: 模型降级
- **WHEN** 主 LLM 调用连续失败 3 次
- **THEN** 自动切换到 fallback 模型，trace 中记录降级事件

### Requirement: CLI 接口——Typer + Rich
系统 SHALL 使用 Typer 构建 CLI，Rich 提供终端格式化输出。

#### Scenario: 执行任务
- **WHEN** 用户运行 `agent run "搜索财报"`
- **THEN** Typer 解析命令，执行完整路由→Agent Loop→返回结果，Rich 格式化输出

#### Scenario: 查看 Trace
- **WHEN** 用户运行 `agent trace <trace_id>`
- **THEN** Rich 以表格形式展示 trace 的所有 spans

#### Scenario: 评测执行
- **WHEN** 用户运行 `agent eval --suite smoke`
- **THEN** 执行评测套件，Rich 展示进度条和结果表格
