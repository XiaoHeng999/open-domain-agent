## 1. 基础设施与数据模型

- [x] 1.1 创建 `.open_agent/memory/` 目录结构（runtime/, profile/, retrieval/, archive/），在 config.yaml 和 MemoryConfig 中添加各层配置参数（路径、token budget、压缩阈值等）
- [x] 1.2 定义数据类放在 `memory/models.py`：`Message`（role, content, timestamp, tokens）、`TaskState`（current_step, finished, termination_flags, rounds_since_todo_update）
- [x] 1.3 实现 `TokenEstimator` 工具类（estimate_tokens 方法，使用 len(text)//4 启发式或 tiktoken），放在 `memory/token_utils.py`

## 2. RuntimeMemory 实现

- [x] 2.1 实现 `RuntimeMemory` 类（继承 MemoryManager），包含 messages 缓冲、rolling_summary、task_state、tool_result_cache 四个核心数据结构
- [x] 2.2 实现 `add_message(role, content)` 方法，添加消息后调用 `_maybe_compress()` 检查 token budget
- [x] 2.3 实现三级压缩策略：Normal（<70% 不压缩）、Compressing（70%-90% rolling summary）、Aggressive（>=90% 限制 retrieval + 截断工具缓存）
- [x] 2.4 实现 `rolling_summary` 管理：将最早 2 轮 raw 对话压缩为 summary 文本，替换为 `[Summary of turns N-M]` 标记；summary 自身超过 budget 30% 时二次压缩
- [x] 2.5 实现 `get_context()` 方法，返回 rolling_summary + 最近 raw messages + task_state，格式化为 list[dict]
- [x] 2.6 实现 tool_result_cache：以 (tool_name, args_hash) 为 key 的 LRU 缓存，超限时清除最早条目
- [x] 2.7 实现 TaskState 的初始化、step 递增、完成标记、todo_update 轮次管理方法

## 3. Session Todo Tool 实现

- [x] 3.1 实现 `TodoManager` 类，包含 items 列表（每项含 content, status, activeForm）、last_update_round
- [x] 3.2 实现 `TodoManager.update(items)` 方法：验证 in_progress 唯一性约束（最多 1 项），替换整个 items 列表，返回渲染文本
- [x] 3.3 实现 `TodoManager.render()` 方法：将 items 渲染为 `[ ]` / `[>]` / `[x]` 格式文本，in_progress 项优先显示 activeForm
- [x] 3.4 实现 `todo` tool handler：接收 items 参数，委托给 TodoManager.update()，返回渲染后的计划文本
- [x] 3.5 将 `todo` tool 注册到 ToolRegistry，定义完整的 input_schema（items array, content/status/activeForm）
- [x] 3.6 实现 ReActLoop 中的 staleness 检测：当 TaskState.rounds_since_todo_update >= 3 且有未完成项时，在 observation 前插入 `<reminder>Refresh your plan before continuing.</reminder>`

## 4. ProfileMemory 实现

- [x] 4.1 实现 `ProfileMemory` 类（继承 MemoryManager），内部使用 sqlite3 管理 SQLite 数据库
- [x] 4.2 实现 SQLite schema 创建（user_profile 表，单行 id=1）和自动初始化逻辑
- [x] 4.3 实现 `load()` 从 SQLite 读取 profile 数据、`save()` 写入更新（原子事务）
- [x] 4.4 实现 `update_preferences()`, `update_constraints()`, `update_tech_stack()`, `add_avoidance_hint()` 方法
- [x] 4.5 实现 `get_injection_text()` 方法，返回结构化文本（200-500 tokens），用于注入 system prompt
- [x] 4.6 实现 avoidance hints 的去重逻辑（基于文本相似度或精确匹配）

## 5. RetrievalMemory 实现

- [x] 5.1 实现 `VectorStore` 类，基于 numpy 的向量存储：write(id, embedding, text, metadata)、query(query_embedding, top_k, metadata_filter)、delete(id)
- [x] 5.2 实现 VectorStore 的持久化：save_to_disk(vectors.npz + metadata.json + texts.json) 和 load_from_disk
- [x] 5.3 实现 `EmbeddingService` 类：优先使用 sentence-transformers（all-MiniLM-L6-v2），回退到 TF-IDF（sklearn）
- [x] 5.4 实现 `RetrievalMemory` 类（继承 MemoryManager），封装 VectorStore + EmbeddingService
- [x] 5.5 实现 Episodic 子层接口：`write_episodic(intent, steps_summary, result, success, ...)` — 生成 embedding + metadata(layer="episodic") 并写入
- [x] 5.6 实现 Semantic 子层接口：`write_semantic(text, category, confidence)` — 生成 embedding + metadata(layer="semantic") 并写入
- [x] 5.7 实现 `query(query_text, top_k=5, layer=None, max_inject_tokens=1500)` 方法：生成 query embedding → 向量检索 → metadata 过滤 → relevance score 排序 → token 截断
- [x] 5.8 实现 query 命中阈值（默认 0.5），score <= threshold 的结果不返回、不注入

## 6. ArchiveMemory 实现

- [x] 6.1 实现 `ArchiveMemory` 类（继承 MemoryManager），管理 JSONL 文件的 append-only 写入
- [x] 6.2 实现 `write(record)` 方法，支持 type=message/tool_call/llm_request/llm_response，自动添加 timestamp
- [x] 6.3 实现 `query(session_id, type=None, limit=None)` debug 查询接口，按行读取 JSONL 并过滤
- [x] 6.4 实现 `replay(session_id)` 方法，返回指定 session 的完整操作记录列表，支持 eval pipeline 使用

## 7. MemoryFactory 重构与集成

- [x] 7.1 重写 `MemoryFactory`：提供 create_runtime_memory()、create_profile_memory()、create_retrieval_memory()、create_archive_memory() 四个工厂方法
- [x] 7.2 更新 `MemoryConfig` 数据类，包含各层的配置参数（token_budget, db_path, store_dir, archive_dir, embedding_model, top_k, max_inject_tokens 等）
- [x] 7.3 更新 `memory/__init__.py`，导出新的类和接口

## 8. Agent 集成

- [x] 8.1 修改 `ReActLoop`：移除 `_conversation_history` 内部 list，改为使用 RuntimeMemory 管理对话上下文和 task state
- [x] 8.2 修改 `ReActLoop._build_messages()`：从 RuntimeMemory.get_context() 获取对话历史，TodoManager.render() 的计划文本注入 MemorySegment
- [x] 8.3 修改 `ReActLoop._execute_action()`：todo tool 调用时重置 TaskState.rounds_since_todo_update
- [x] 8.4 修改 `AgentRuntime.run()`：在任务完成后写入 RetrievalMemory episodic 记录、更新 ProfileMemory avoidance hints、写入 ArchiveMemory 操作日志
- [x] 8.5 修改 `AgentRuntime.on_start()`：注册 todo tool 到 ToolRegistry，创建 TodoManager 实例
- [x] 8.6 重写 `prompt/segments.py` 的 `MemorySegment`：按层渲染（RuntimeMemory context + TodoManager plan + ProfileMemory injection + RetrievalMemory results）
- [x] 8.7 修改 `PromptBuilder.build()`：传入所有 memory 层的 context，触发 RetrievalMemory query
- [x] 8.8 更新 `config.yaml` 添加 memory 各层配置 + todo staleness_rounds 参数

## 9. 测试

- [x] 9.1 为 RuntimeMemory 编写单元测试：消息添加、token 计算、三级压缩、rolling summary、task state、tool cache
- [x] 9.2 为 TodoManager 编写单元测试：整份重写、in_progress 唯一性、渲染格式、空计划处理
- [x] 9.3 为 ProfileMemory 编写单元测试：SQLite CRUD、avoidance hints 去重、injection text 格式
- [x] 9.4 为 RetrievalMemory 编写单元测试：向量写入/检索、episodic/semantic 子层、metadata 过滤、token 截断
- [x] 9.5 为 ArchiveMemory 编写单元测试：JSONL 写入/读取、session 隔离、replay
- [x] 9.6 为 MemoryFactory 编写单元测试：工厂方法创建各层实例
- [x] 9.7 编写集成测试：ReActLoop 使用 RuntimeMemory、todo tool 调用与 staleness 提醒、PromptBuilder 注入 MemorySegment、端到端 memory 流程
