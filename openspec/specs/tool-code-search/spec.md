## ADDED Requirements

### Requirement: Search 工具 grep 操作
`search` 工具 SHALL 提供 `action="grep"` 操作，基于 ripgrep 在工作区内搜索文件内容。支持正则表达式、文件类型过滤和结果数量限制。

#### Scenario: 基本正则搜索
- **WHEN** Agent 调用 `search` 工具并传入 `action="grep"`、`pattern="TODO"`、`path="src/"`
- **THEN** SHALL 使用 ripgrep 搜索 `src/` 目录下包含 "TODO" 的文件
- **THEN** SHALL 返回匹配行及行号，格式为 `file:line:content`

#### Scenario: 带文件类型过滤的搜索
- **WHEN** Agent 调用 `search` 工具并传入 `action="grep"`、`pattern="def execute"`、`file_type="py"`
- **THEN** SHALL 仅搜索 `.py` 文件

#### Scenario: ripgrep 不可用时的降级
- **WHEN** 系统中未安装 `rg` 命令
- **THEN** SHALL 返回友好的错误信息，提示安装 ripgrep

### Requirement: Search 工具 glob 操作
`search` 工具 SHALL 提供 `action="glob"` 操作，基于文件名模式匹配查找文件。支持 glob 模式如 `**/*.py`。

#### Scenario: 按模式匹配文件
- **WHEN** Agent 调用 `search` 工具并传入 `action="glob"`、`pattern="**/*.py"`、`path="src/"`
- **THEN** SHALL 返回 `src/` 目录下所有 `.py` 文件路径列表

#### Scenario: 无匹配结果
- **WHEN** glob 模式没有匹配到任何文件
- **THEN** SHALL 返回空列表提示

### Requirement: Search 工具安全属性
`search` 工具 SHALL 标记为 `read_only=True`，`safety_checks` SHALL 包含 `["path"]`。

#### Scenario: 安全检查标记
- **WHEN** `search` 工具注册到 ToolRegistry
- **THEN** `read_only` SHALL 为 True
- **THEN** `safety_checks` SHALL 包含 `["path"]`

### Requirement: Search 工具参数约束
`search` 工具 SHALL 对结果数量进行限制，默认最大返回 100 条匹配，防止输出溢出。

#### Scenario: 结果数量限制
- **WHEN** grep 搜索匹配超过 100 条结果
- **THEN** SHALL 截断返回前 100 条并附加截断提示
