## Why

现有 memory 系统存在三方面结构性缺陷：(1) WorkingMemory 和 session `_conversation_history` 功能重叠——WorkingMemory 被创建但在运行时从未被使用，实际的短期上下文由 ReActLoop 内部一个无压缩机制的 plain list 管理，长对话会导致 token 爆炸；(2) EpisodicStore、UserProfile、SemanticKB 仅有 in-memory stub，进程退出即丢失，且无向量检索能力；(3) 缺少 Archive 层，无法回放历史用于 debug 和 eval。需要将 memory 重构为 4 层架构（Runtime / Profile / Retrieval / Archive），各自有明确的职责边界、生命周期、token 管理策略和持久化方案。

## What Changes

- **BREAKING** 合并 WorkingMemory + session `_conversation_history` → `RuntimeMemory`，统一管理对话缓冲、任务状态、工具结果缓存、rolling summary 压缩
- RuntimeMemory 引入 token budget 管理：超限时删除最早 raw 对话并替换为 summary 标记，限制 retrieval 注入量和 scratchpad 大小
- 新增 `todo` tool（注册到 ToolRegistry），LLM 主动调用以管理当前 session 的多步任务计划；计划状态通过 MemorySegment 注入 prompt；连续 3 轮未更新时自动提醒
- 重构 UserProfile → `ProfileMemory`，使用 SQLite 持久化，自动注入 system prompt，不存储对话历史
- 合并 EpisodicStore + SemanticKB → `RetrievalMemory`（Episodic 子层 + Semantic 子层），共享 vector store 后端，仅 query 命中时注入 prompt，限制 top_k 和 max_inject_tokens
- 新增 `ArchiveMemory` 冷存储层，保存原始日志/全量工具调用/原始 prompt-response，用于 debug/eval/replay，不参与推理
- 所有持久化数据统一存放至 `.open_agent/memory/` 目录，按层分子目录

## Capabilities

### New Capabilities
- `runtime-memory`: 短期运行时记忆层——对话缓冲、rolling summary、token budget 管理与自动压缩
- `session-todo`: 会话级任务计划 tool——LLM 通过 `todo` 工具显式管理多步任务计划（pending/in_progress/completed 状态），整份重写模式，计划状态注入 prompt，连续 3 轮未更新时自动提醒
- `profile-memory`: 稳定用户状态层——偏好/约束/风格/技术栈建模，SQLite 持久化，每次自动注入 system prompt
- `retrieval-memory`: 可检索长期记忆层——Episodic + Semantic 双子层，vector store 检索，query 命中时注入 prompt，top_k 和 max_tokens 限制
- `archive-memory`: 冷存储层——原始日志、全量工具调用、prompt/response 原文，用于 debug/eval/replay，不参与推理

### Modified Capabilities
- `memory-management`: 移除 WorkingMemory/EpisodicStore/UserProfile/SemanticKB 的旧实现，MemoryFactory 改为创建 4 个新层；MemorySegment 重写为按层渲染；ReActLoop 移除内部 `_conversation_history`，改用 RuntimeMemory

## Impact

- **代码变更**: `src/open_agent/memory/` 全部重写（working.py → runtime.py, episodic.py + semantic.py → retrieval.py, profile.py 重构, 新增 archive.py），`factory.py` 重写；新增 `src/open_agent/tools/todo.py`（TodoManager + tool 注册）
- **集成变更**: `agent/react.py` 移除 `_conversation_history`，改为从 RuntimeMemory 读写上下文，新增 staleness 检测逻辑；`prompt/segments.py` 的 MemorySegment 重写，新增 TodoSegment；`runtime.py` 注册 todo tool；`registry.py` 新增 todo tool
- **新增依赖**: `sqlite3`（标准库）、向量存储后端（numpy 余弦相似度自实现）
- **存储**: 新增 `.open_agent/memory/` 目录（runtime/ session 级别、profile.sqlite、retrieval/ vector data、archive/ JSONL 日志）
- **配置**: `config.yaml` 和 `MemoryConfig` 新增各层的 token budget、路径、压缩参数
