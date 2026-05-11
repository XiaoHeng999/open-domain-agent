## ADDED Requirements

### Requirement: ArchiveMemory JSONL 冷存储
系统 SHALL 以 JSONL 格式冷存储所有操作记录，每个 session 生成一个 JSONL 文件。文件路径为 `.open_agent/memory/archive/{session_id}.jsonl`。

#### Scenario: 记录用户消息
- **WHEN** 用户发送一条消息
- **THEN** ArchiveMemory 写入一行 JSON：`{"type": "message", "role": "user", "content": "...", "tokens": N, "ts": "ISO8601"}`

#### Scenario: 记录工具调用
- **WHEN** Agent 调用一个工具
- **THEN** ArchiveMemory 写入一行 JSON：`{"type": "tool_call", "tool": "name", "args": {...}, "result": "...", "duration_ms": N, "ts": "ISO8601"}`

#### Scenario: 记录 LLM 请求
- **WHEN** Agent 向 LLM 发送请求
- **THEN** ArchiveMemory 写入一行 JSON：`{"type": "llm_request", "model": "...", "prompt_tokens": N, "ts": "ISO8601"}`

#### Scenario: 记录 LLM 响应
- **WHEN** LLM 返回响应
- **THEN** ArchiveMemory 写入一行 JSON：`{"type": "llm_response", "content": "...", "completion_tokens": N, "finish_reason": "...", "ts": "ISO8601"}`

### Requirement: ArchiveMemory 不参与推理
系统 SHALL 确保 ArchiveMemory 不参与 PromptBuilder 的 prompt 组装，不注入任何 context。ArchiveMemory 仅提供 write 和 debug 查询接口。

#### Scenario: PromptBuilder 不读取 Archive
- **WHEN** PromptBuilder 构建消息列表
- **THEN** ArchiveMemory 的数据不在 messages 列表中出现

#### Scenario: 仅 debug 查询接口
- **WHEN** 开发者或 eval pipeline 需要回放历史
- **THEN** 可通过 `archive.query(session_id, type=None, limit=N)` 查询指定 session 的操作记录

### Requirement: ArchiveMemory 会话隔离
系统 SHALL 按 session_id 隔离存储，每个 session 的记录在独立 JSONL 文件中。

#### Scenario: 新 session 创建新文件
- **WHEN** 新 session 开始
- **THEN** 在 archive 目录下创建新的 `{session_id}.jsonl` 文件

#### Scenario: 旧 session 文件保留
- **WHEN** 系统启动时
- **THEN** 不删除历史 session 的 JSONL 文件，保留所有历史记录用于 debug/eval/replay

### Requirement: ArchiveMemory Replay 支持
系统 SHALL 支持从 JSONL 文件回放历史 session，用于 eval pipeline。

#### Scenario: 回放指定 session
- **WHEN** eval pipeline 指定一个 session_id
- **THEN** 系统读取对应 JSONL 文件，按时间顺序返回所有操作记录，可用于重现 Agent 行为

#### Scenario: 回放时过滤类型
- **WHEN** eval pipeline 指定 session_id 和 type 过滤条件（如 "tool_call"）
- **THEN** 系统仅返回指定类型的操作记录
