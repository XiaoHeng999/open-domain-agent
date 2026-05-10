## ADDED Requirements

### Requirement: 技能文件格式——Markdown + YAML Frontmatter
系统 SHALL 支持以 Markdown 文件 + YAML frontmatter 元数据定义技能。YAML 元数据包含 name、description、domain、tools（所需工具列表）、trigger（触发关键词列表）。

#### Scenario: 技能文件解析
- **WHEN** 框架扫描到技能文件 `code-review.md`，其 frontmatter 为 `{name: "code-review", domain: "coding", tools: ["file_read", "search"], trigger: ["审查代码", "code review"]}`
- **THEN** 系统解析出完整元数据，Markdown 正文作为技能内容

#### Scenario: 无效技能文件跳过
- **WHEN** 扫描到的 Markdown 文件缺少必要 frontmatter 字段（如缺少 name 或 domain）
- **THEN** 系统跳过该文件并在日志中记录警告，不阻塞启动

### Requirement: 内置技能 + 工作区自定义技能
系统 SHALL 支持两类技能来源：框架内置技能（随代码分发）和工作区自定义技能（`.skills/` 目录）。两者使用相同的格式和加载逻辑。

#### Scenario: 内置技能自动加载
- **WHEN** 框架启动时
- **THEN** 自动扫描内置技能目录，注册所有有效技能到 SkillRegistry

#### Scenario: 工作区自定义技能发现
- **WHEN** 当前工作目录下存在 `.skills/` 目录且包含 Markdown 文件
- **THEN** 框架扫描并注册这些自定义技能，与内置技能享有相同地位

### Requirement: 动态技能注册表（SkillRegistry）
系统 SHALL 实现动态技能注册表，支持运行时注册、注销、查询技能。

#### Scenario: 注册新技能
- **WHEN** 开发者调用 `skill_registry.register("my-skill", skill_meta, content_loader)`
- **THEN** 技能被注册到注册表，后续可通过 domain 和 trigger 匹配

#### Scenario: 运行时注销技能
- **WHEN** 开发者调用 `skill_registry.unregister("my-skill")`
- **THEN** 技能从注册表移除，后续不再匹配

#### Scenario: 查询可用技能
- **WHEN** 查询某个 domain 下的所有技能
- **THEN** 返回该 domain 下所有已注册技能的元数据列表

### Requirement: 技能按需加载（Lazy Loading）
系统 SHALL 仅在技能匹配到任务时才加载 Markdown 正文内容，注册阶段只加载元数据。

#### Scenario: 注册时不加载内容
- **WHEN** 框架启动并注册 20 个技能
- **THEN** 只读取每个文件的 YAML frontmatter，不读取 Markdown 正文，内存开销最小

#### Scenario: 匹配时加载内容
- **WHEN** 路由阶段匹配到 "code-review" 技能
- **THEN** 系统此时才读取该技能的 Markdown 正文并注入 Agent 的 system prompt

#### Scenario: 任务完成后清理
- **WHEN** 使用技能的任务执行完成
- **THEN** 技能内容从 Agent context 中移除，释放 token 空间

### Requirement: 技能匹配——Domain + Trigger 双重匹配
系统 SHALL 在路由阶段基于 domain 和 trigger 关键词进行技能匹配。

#### Scenario: Domain + Trigger 匹配
- **WHEN** 请求被路由到 coding domain，用户输入包含 "审查代码"
- **THEN** 系统匹配到 code-review 技能，加载其内容注入 prompt

#### Scenario: 无匹配技能
- **WHEN** 请求的 domain 下没有匹配 trigger 的技能
- **THEN** Agent 正常执行，不注入任何技能内容
