## ADDED Requirements

### Requirement: 提示词模板集中管理
系统 SHALL 将所有提示词文本模板（包括各段的静态模板字符串、分隔符格式、默认角色定义等）集中存放在 `src/open_agent/prompt/prompt.py` 文件中。各 Segment 类从该文件导入模板，自身不包含任何硬编码提示词字符串。

#### Scenario: 模板集中存储
- **WHEN** 开发者需要修改核心身份提示词的措辞
- **THEN** 只需修改 `prompt.py` 中的 `CORE_IDENTITY_TEMPLATE` 常量，无需改动任何 Segment 类代码

#### Scenario: Segment 从集中文件导入
- **WHEN** CoreIdentitySegment 的 build() 方法需要生成内容
- **THEN** 它从 `prompt.py` 导入 `CORE_IDENTITY_TEMPLATE` 并填充动态变量，不使用内联字符串

### Requirement: 段分隔符与精简输出
系统 SHALL 为每个 Segment 的输出使用 XML-style 标记（`<segment_type>` / `</segment_type>`）包裹内容，段与段之间使用 `SEGMENT_SEPARATOR` 分隔。每段内容 SHALL 保持精简，避免冗余描述。

#### Scenario: 段输出格式
- **WHEN** ToolListSegment build() 返回内容
- **THEN** 输出格式为 `<tool_list>\n{精简工具描述}\n</tool_list>`，每个工具只包含 name + description + parameters

#### Scenario: 完整流水线组装
- **WHEN** PromptBuilder.build() 被调用且所有段均有内容
- **THEN** 返回按顺序拼接的完整 system prompt，各段由 XML-style 标记包裹，段间用 `SEGMENT_SEPARATOR` 分隔

#### Scenario: 空段自动跳过
- **WHEN** 某个段（如 Memory 段）当前无内容
- **THEN** 该段不输出任何内容（包括 XML 标记和分隔符），不影响其他段的输出

### Requirement: 稳定段与动态段区分
系统 SHALL 将 6 个段区分为稳定段（stable）和动态段（dynamic）。稳定段在启动时生成一次并缓存，仅在显式 invalidate 时重新生成；动态段在每次 build() 调用时重新生成。

#### Scenario: 稳定段缓存生效
- **WHEN** CoreIdentitySegment 首次生成后，连续调用 3 次 build()
- **THEN** CoreIdentitySegment 的内容只生成 1 次，后续 2 次使用缓存

#### Scenario: 稳定段失效重建
- **WHEN** 调用 builder.invalidate("core_identity") 后再次调用 build()
- **THEN** CoreIdentitySegment 重新生成内容并更新缓存

#### Scenario: 动态段每次刷新
- **WHEN** 连续调用 3 次 build()
- **THEN** ToolListSegment、SkillsSegment、MemorySegment、DynamicEnvSegment 每次都重新生成

### Requirement: 核心身份段（CoreIdentitySegment）
系统 SHALL 实现 CoreIdentitySegment，生成 Agent 的角色定义和行为准则。该段为稳定段，内容来自配置文件和默认模板。

#### Scenario: 默认身份信息
- **WHEN** 未提供自定义身份配置
- **THEN** 生成默认的 Agent 角色定义，包含框架名称、核心能力和行为边界

#### Scenario: 自定义身份信息
- **WHEN** 配置中提供了 custom_identity 字段
- **THEN** 使用自定义身份信息替代默认模板

### Requirement: 工具列表段（ToolListSegment）
系统 SHALL 实现 ToolListSegment，渲染当前可用工具的 JSON Schema 描述。该段为动态段，支持逻辑 agent 分层时的工具集切换。

#### Scenario: 全量工具渲染
- **WHEN** 逻辑 agent 未指定工具过滤条件
- **THEN** 渲染 ToolRegistry 中所有已注册工具的名称、描述和参数 Schema

#### Scenario: 按角色过滤工具
- **WHEN** 逻辑 agent 指定了 tool_filter（如 tags=["coding"]）
- **THEN** 仅渲染匹配过滤条件的工具子集

#### Scenario: 工具变更实时反映
- **WHEN** 运行时新注册或注销了工具
- **THEN** 下一次 build() 调用时工具列表段反映最新状态

### Requirement: Skills 元信息段（SkillsSegment）
系统 SHALL 实现 SkillsSegment，注入当前任务匹配到的技能指令内容。该段为动态段，内容由 SkillMatcher 在路由阶段决定。

#### Scenario: 匹配技能注入
- **WHEN** 路由阶段匹配到 2 个技能（code-review, search-analyze）
- **THEN** SkillsSegment 输出这 2 个技能的名称和完整指令内容

#### Scenario: 无匹配技能
- **WHEN** 路由阶段未匹配到任何技能
- **THEN** SkillsSegment 输出空内容，不占用 token

### Requirement: Memory 内容段（MemorySegment）
系统 SHALL 实现 MemorySegment，注入工作记忆、历史摘要和用户偏好。该段为动态段，每轮对话刷新。

#### Scenario: 完整 Memory 注入
- **WHEN** WorkingMemory 有历史对话、EpisodicStore 有任务摘要、UserProfileState 有偏好记录
- **THEN** MemorySegment 输出包含当前对话上下文、相关历史摘要和用户偏好的内容

#### Scenario: 空 Memory
- **WHEN** 新会话首次调用且所有 Memory 组件为空
- **THEN** MemorySegment 输出空内容

### Requirement: CLAUDE.md 指令链段（ClaudemdSegment）
系统 SHALL 实现 ClaudemdSegment，加载项目级指令文件。该段为混合段（基础指令稳定 + 项目指令动态）。

#### Scenario: 全局指令加载
- **WHEN** 存在全局 CLAUDE.md 配置文件
- **THEN** 加载并注入全局指令内容

#### Scenario: 项目指令加载
- **WHEN** 当前工作目录下存在 CLAUDE.md 或 .claude/ 目录下的指令文件
- **THEN** 加载并注入项目级指令，追加在全局指令之后

### Requirement: 动态环境信息段（DynamicEnvSegment）
系统 SHALL 实现 DynamicEnvSegment，输出当前环境信息。该段为动态段，每轮对话刷新。

#### Scenario: 环境信息输出
- **WHEN** build() 被调用
- **THEN** 输出包含当前日期时间、操作系统平台、工作目录路径等环境信息

### Requirement: Token 预算估算
系统 SHALL 为每个段提供 token 估算方法，支持在 build() 时检查总 token 量并在超限时按优先级截断。

#### Scenario: Token 未超限
- **WHEN** 6 段总 token 估算值 < 预算上限
- **THEN** 输出完整 6 段内容

#### Scenario: Token 超限截断
- **WHEN** 6 段总 token 估算值 > 预算上限
- **THEN** 按优先级从低到高截断（优先截断 Memory 段的早期内容，保留 Core Identity 和 Tool List）

### Requirement: PromptBuilder 集成到 ReActLoop
系统 SHALL 修改 ReActLoop 使用 PromptBuilder 替代硬编码的 system prompt。ReActLoop 构造时接收 PromptBuilder 实例。

#### Scenario: ReActLoop 使用 Pipeline
- **WHEN** AgentRuntime 创建 ReActLoop 并传入 PromptBuilder
- **THEN** ReActLoop._build_messages() 调用 builder.build(context) 获取完整 system prompt，替代原有硬编码字符串
