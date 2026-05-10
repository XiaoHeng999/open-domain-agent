## MODIFIED Requirements

### Requirement: 技能文件格式——Markdown + YAML Frontmatter
系统 SHALL 支持以 Markdown 文件 + YAML frontmatter 元数据定义技能。YAML 元数据包含 name、description、domain、tools（所需工具列表）、trigger（触发关键词列表）。同时 SHALL 支持以目录形式组织技能包，目录内包含 .md 定义文件和可选 .py handler 文件。

#### Scenario: 单文件技能解析（现有行为保持）
- **WHEN** 框架扫描到技能文件 `code-review.md`，其 frontmatter 为 `{name: "code-review", domain: "coding", tools: ["file_read", "search"], trigger: ["审查代码", "code review"]}`
- **THEN** 系统解析出完整元数据，Markdown 正文作为技能内容

#### Scenario: 目录技能包解析（新增）
- **WHEN** 框架扫描到技能目录 `weather/`，包含 `weather.md`（含 YAML frontmatter）和 `weather.py`（含 register 函数）
- **THEN** 系统解析 .md 的元数据和指令内容，同时加载 .py 中的 register() 函数并调用以注册工具

#### Scenario: 无效技能文件跳过
- **WHEN** 扫描到的 Markdown 文件缺少必要 frontmatter 字段（如缺少 name 或 domain）
- **THEN** 系统跳过该文件并在日志中记录警告，不阻塞启动

### Requirement: 技能按需加载（Lazy Loading）
系统 SHALL 仅在技能匹配到任务时才加载 Markdown 正文内容，注册阶段只加载元数据。对于目录技能包，.py handler 文件 SHALL 在注册阶段加载并调用 register() 函数，.md 指令内容仍按需加载。

#### Scenario: 注册时不加载指令内容
- **WHEN** 框架启动并注册 20 个技能
- **THEN** 只读取每个文件/目录的 YAML frontmatter，不读取 Markdown 指令正文，内存开销最小

#### Scenario: 目录技能注册时加载 handler
- **WHEN** 框架注册一个目录技能包（含 .py handler）
- **THEN** 在注册阶段调用 handler 的 register() 函数将工具注册到 ToolRegistry

#### Scenario: 匹配时加载指令内容
- **WHEN** 路由阶段匹配到 "weather" 技能
- **THEN** 系统此时才读取该技能的 Markdown 正文并注入 Agent 的 system prompt

#### Scenario: 任务完成后清理
- **WHEN** 使用技能的任务执行完成
- **THEN** 技能指令内容从 Agent context 中移除，释放 token 空间
