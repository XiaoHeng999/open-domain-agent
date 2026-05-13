## ADDED Requirements

### Requirement: ReadFileTool 文件读取工具
系统 SHALL 提供 `read_file` 工具，读取指定路径的文件内容并返回字符串。支持可选的 offset 和 limit 参数实现分页读取。

#### Scenario: 读取完整文件
- **WHEN** LLM 调用 `read_file` 参数 `{"path": "src/main.py"}`
- **THEN** 工具读取文件内容并返回完整文本

#### Scenario: 分页读取
- **WHEN** LLM 调用 `read_file` 参数 `{"path": "large.log", "offset": 100, "limit": 50}`
- **THEN** 工具从第 100 行开始读取 50 行并返回

#### Scenario: 文件不存在
- **WHEN** LLM 调用 `read_file` 参数 `{"path": "nonexistent.txt"}`
- **THEN** 工具返回 `"Error: File not found: nonexistent.txt"`

#### Scenario: 路径超出工作区
- **WHEN** LLM 调用 `read_file` 参数 `{"path": "/etc/passwd"}`
- **THEN** 工具返回路径遍历错误（由 SafetyManager 拦截）

### Requirement: WriteFileTool 文件写入工具
系统 SHALL 提供 `write_file` 工具，将内容写入指定文件路径。自动创建不存在的父目录。

#### Scenario: 创建新文件
- **WHEN** LLM 调用 `write_file` 参数 `{"path": "src/new_module.py", "content": "# new module\n"}`
- **THEN** 工具创建文件（含父目录）并写入内容，返回成功确认

#### Scenario: 覆盖现有文件
- **WHEN** LLM 调用 `write_file` 参数 `{"path": "config.yaml", "content": "key: value\n"}`
- **THEN** 工具覆盖文件内容，返回成功确认

#### Scenario: 路径超出工作区
- **WHEN** LLM 调用 `write_file` 参数 `{"path": "/etc/evil.conf", "content": "hacked"}`
- **THEN** 工具返回路径安全错误

### Requirement: EditFileTool 文件编辑工具
系统 SHALL 提供 `edit_file` 工具，在文件中执行精确的字符串替换（find-and-replace）。

#### Scenario: 成功替换
- **WHEN** LLM 调用 `edit_file` 参数 `{"path": "main.py", "old_string": "print('hello')", "new_string": "print('world')"}`
- **THEN** 工具替换匹配文本并返回成功确认

#### Scenario: 匹配不唯一
- **WHEN** `old_string` 在文件中出现多次
- **THEN** 工具返回错误 `"Error: old_string matches 3 times. Provide more context to make it unique."`

#### Scenario: 未找到匹配
- **WHEN** `old_string` 在文件中不存在
- **THEN** 工具返回错误 `"Error: old_string not found in file"`

### Requirement: ListDirTool 目录列表工具
系统 SHALL 提供 `list_dir` 工具，列出指定目录的内容，每行显示名称和类型标识（`[DIR]` 或 `[FILE]`）。

#### Scenario: 列出目录
- **WHEN** LLM 调用 `list_dir` 参数 `{"path": "src"}`
- **THEN** 工具返回目录内容列表，每行格式如 `[DIR]  agent/` 或 `[FILE] main.py`

#### Scenario: 空目录
- **WHEN** LLM 调用 `list_dir` 参数 `{"path": "empty_dir/"}`
- **THEN** 工具返回 `"(empty directory)"`

#### Scenario: 目录不存在
- **WHEN** LLM 调用 `list_dir` 参数 `{"path": "nonexistent/"}`
- **THEN** 工具返回 `"Error: Directory not found: nonexistent/"`

### Requirement: 文件系统工具工作区限制
系统 SHALL 将所有文件系统工具的操作限制在配置的工作区目录内。工具构造函数接收 `workspace: str` 参数。

#### Scenario: 工作区内操作放行
- **WHEN** 工具配置 workspace="/project" 且调用 path="/project/src/main.py"
- **THEN** 路径解析后在工作区内，操作正常执行

#### Scenario: 工作区外操作拒绝
- **WHEN** 工具配置 workspace="/project" 且调用 path="/tmp/evil.txt"
- **THEN** 路径解析后超出工作区，返回安全错误

## MODIFIED Requirements (security-hardening-and-critical-fixes)

### Requirement: Filesystem Workspace Restriction
All filesystem tools MUST enforce workspace boundary checking using `Path.resolve()` (which resolves symlinks) and `Path.is_relative_to()` (which prevents boundary bugs like `/data/app` matching `/data/application`). The SafetyManager MUST reject any path that resolves outside the configured workspace, including paths that traverse through symlinks pointing outside the workspace.

#### Scenario: Symlink pointing outside workspace
- **WHEN** a symlink inside `/workspace` points to `/etc/passwd`
- **THEN** read_file on that symlink path returns a security error

#### Scenario: Similar-prefix path rejected
- **WHEN** workspace is `/data/app` and path is `/data/application/secret`
- **THEN** the operation is rejected (not falsely matched by startswith)

#### Scenario: Normal path within workspace
- **WHEN** workspace is `/data/app` and path is `/data/app/src/main.py`
- **THEN** the operation proceeds normally
