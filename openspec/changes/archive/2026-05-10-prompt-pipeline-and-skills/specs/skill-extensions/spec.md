## ADDED Requirements

### Requirement: 技能包目录结构
系统 SHALL 支持以目录形式组织技能包，每个目录包含一个 .md 定义文件和一个 .py handler 文件。目录名即为技能名。

#### Scenario: 目录技能发现
- **WHEN** 框架扫描技能目录时发现子目录 `weather/` 包含 `weather.md` 和 `weather.py`
- **THEN** 系统将其识别为一个完整技能包，同时加载元数据、指令内容和 Python handler

#### Scenario: 缺少 handler 文件的目录技能
- **WHEN** 扫描到的技能目录只包含 .md 文件，无 .py 文件
- **THEN** 系统仅加载技能元数据和指令内容，不注册额外工具（视为纯指令型技能）

#### Scenario: 缺少定义文件的目录
- **WHEN** 扫描到的目录只包含 .py 文件，无 .md 文件
- **THEN** 系统跳过该目录并记录警告日志

### Requirement: 技能 Python Handler 注册
系统 SHALL 支持技能包中的 .py 文件导出 `register(registry: ToolRegistry)` 函数，在技能加载时自动调用以注册该技能所需的工具。

#### Scenario: Handler 工具注册
- **WHEN** 技能 `weather` 被加载，其 `weather.py` 导出了 `register(registry)` 函数
- **THEN** 系统调用 `register(registry)` 将天气查询等工具注册到全局 ToolRegistry

#### Scenario: Handler 注册失败不阻塞启动
- **WHEN** 技能 handler 的 `register()` 函数抛出异常
- **THEN** 系统记录错误日志，跳过该技能的工具注册，不阻塞其他技能加载

### Requirement: skill-creator 技能包
系统 SHALL 提供 skill-creator 技能包骨架，包含 .md 和 .py 文件。该技能用于辅助创建新技能。

#### Scenario: skill-creator 目录结构
- **WHEN** 框架启动时扫描 builtin 技能目录
- **THEN** 发现 `skill-creator/skill-creator.md` 和 `skill-creator/skill-creator.py`，正确加载技能

### Requirement: summarize 技能包
系统 SHALL 提供 summarize 技能包骨架，包含 .md 和 .py 文件。该技能用于内容摘要生成。

#### Scenario: summarize 目录结构
- **WHEN** 框架启动时扫描 builtin 技能目录
- **THEN** 发现 `summarize/summarize.md` 和 `summarize/summarize.py`，正确加载技能

### Requirement: weather 技能包
系统 SHALL 提供 weather 技能包骨架，包含 .md 和 .py 文件。该技能用于天气查询。

#### Scenario: weather 目录结构
- **WHEN** 框架启动时扫描 builtin 技能目录
- **THEN** 发现 `weather/weather.md` 和 `weather/weather.py`，正确加载技能

### Requirement: github 技能包
系统 SHALL 提供 github 技能包骨架，包含 .md 和 .py 文件。该技能用于 GitHub 操作集成。

#### Scenario: github 目录结构
- **WHEN** 框架启动时扫描 builtin 技能目录
- **THEN** 发现 `github/github.md` 和 `github/github.py`，正确加载技能

### Requirement: wechat-mp-cn 技能包
系统 SHALL 提供 wechat-mp-cn 技能包骨架，包含 .md 和 .py 文件。该技能用于微信公众号内容操作。

#### Scenario: wechat-mp-cn 目录结构
- **WHEN** 框架启动时扫描 builtin 技能目录
- **THEN** 发现 `wechat-mp-cn/wechat-mp-cn.md` 和 `wechat-mp-cn/wechat-mp-cn.py`，正确加载技能
