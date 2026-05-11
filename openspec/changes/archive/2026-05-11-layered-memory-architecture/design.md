## Context

当前 open_agent 的 memory 系统有 4 个独立模块（WorkingMemory、EpisodicStore、UserProfileState、SemanticKB），但存在严重问题：

1. **WorkingMemory 从未被使用**：`AgentRuntime` 创建了 WorkingMemory 实例，但 `ReActLoop` 使用内部 `_conversation_history`（plain list）管理会话上下文，无压缩机制
2. **无持久化**：EpisodicStore、UserProfile、SemanticKB 仅有 in-memory dict，进程退出即丢失
3. **SemanticKB 是空 stub**：`query()` 始终返回 `[]`
4. **MemorySegment 永远为空**：PromptBuilder 从未接收 memory context

本设计将 memory 重构为 4 层架构，每层有独立职责、存储后端和生命周期。

## Goals / Non-Goals

**Goals:**
- 合并 WorkingMemory + session history 为统一的 RuntimeMemory，具备 rolling summary 和 token budget 管理
- ProfileMemory 使用 SQLite 持久化，每次自动注入 system prompt
- RetrievalMemory 支持 Episodic + Semantic 双子层，基于向量检索，仅命中时注入 prompt
- ArchiveMemory 以 JSONL 格式冷存储全量操作日志
- 所有持久化数据统一至 `.open_agent/memory/` 目录

**Non-Goals:**
- 不实现分布式/跨机器 memory 共享
- 不实现多用户隔离（当前单用户场景）
- 不实现 memory 的 UI 管理界面
- 不引入重型向量数据库（如 Milvus、Pinecone），优先轻量自实现
- 不实现 Profile 的自动学习/推理更新（仅支持显式写入）

## Decisions

### D0: Session Todo 方案——Tool 而非 RuntimeMemory 子组件

**选择**: 将 session 级任务计划实现为 `todo` tool，注册在 ToolRegistry 中，LLM 通过 `tool_name: "todo"` 显式调用。

**备选方案**: 嵌入 RuntimeMemory 作为子组件，通过解析 LLM 输出特殊字段触发更新。

**理由**: ReAct 循环的核心原则是 agent 与外部世界的所有交互必须通过 tool call 完成。Tool 方案的优势：

1. **Agent 自主权**：LLM 在 `_tool_schema()` 中看到 `todo` 工具，主动决定何时更新计划，而非依赖外部启发式触发
2. **可追溯性**：每次计划更新是一个完整的 ReAct 步骤（Thought → Action(todo) → Observation(渲染后的计划)），出现在 step history 和 trace 中
3. **符合行业实践**：Claude Code 的 TaskCreate/TaskUpdate/TaskList、OpenAI function calling pattern 的 scratchpad tool 都是同样的 tool-first 设计

**交互模式**:
```
用户提出多步任务
  → LLM 在 thought 中决定"需要制定计划"
  → LLM 调用 todo tool，传入完整 items 列表
  → Tool 返回渲染后的计划文本
  → 计划文本注入后续 prompt
  → 每完成一步，LLM 再次调用 todo 更新状态
  → 连续 3 轮未更新 → ReActLoop 注入 <reminder>
```

**整份重写 vs 增量更新**: 选择整份重写——LLM 每次调用传入完整 items 列表。理由：避免增量操作带来的状态不一致问题，且 LLM 生成完整 JSON 的成本与增量 patch 相当，但正确性更高。

### D1: Vector Store 后端选择——自实现 numpy 余弦相似度

**选择**: 使用 `numpy` + `sentence-transformers`（或纯 numpy 随机投影）实现向量检索，数据存储为本地文件。

**备选方案**:
- ChromaDB：Python 原生，轻量，但引入额外依赖且版本迭代快
- FAISS：高性能但编译复杂，安装问题多
- Qdrant：偏重，适合生产级部署

**理由**: 当前阶段不需要生产级向量数据库。numpy 余弦相似度足以处理万级文档检索，零额外依赖（numpy 已是标准科学计算库）。metadata 过滤可在 Python 层实现。后续如需升级可替换为 ChromaDB 接口。

**存储格式**: `.open_agent/memory/retrieval/vectors.npz`（numpy 压缩格式）+ `.open_agent/memory/retrieval/metadata.json`。每条记录包含 `id`, `embedding`, `text`, `metadata`（含 `layer: episodic|semantic`）。

### D2: RuntimeMemory 的压缩策略——Rolling Summary + Token Budget

**选择**: 三级压缩策略：
1. **Normal**: 当 `total_tokens < budget * 0.7` 时，保留全部 raw messages
2. **Compressing**: 当 `budget * 0.7 <= total_tokens < budget * 0.9` 时，将最早的 raw 对话轮次压缩为 summary，替换为 `[Summary of turns 1-N]` 标记
3. **Aggressive**: 当 `total_tokens >= budget * 0.9` 时，额外限制 retrieval 注入量，截断 scratchpad

**压缩流程**:
```
每轮对话后 → 计算 total_tokens
  → 超 70% 阈值 → 取最早 2 轮 raw 对话 → LLM 生成/追加到 rolling_summary → 删除原始轮次 → 插入 summary 标记
  → 超 90% 阈值 → 限制 retrieval top_k → 截断工具结果缓存
```

**TaskState 结构**（精简版——计划管理由 todo tool 负责，TaskState 仅跟踪执行层面）:
```python
@dataclass
class TaskState:
    current_step: int                # ReAct 迭代计数
    finished: bool
    termination_flags: list[str]     # 终止条件
    rounds_since_todo_update: int    # 距上次 todo 更新的轮次
```

TaskState 始终保留在 RuntimeMemory 中，不参与压缩。计划内容由 TodoManager 管理，通过 MemorySegment 注入。

### D3: ProfileMemory 存储——SQLite

**选择**: 使用 SQLite（标准库）存储用户画像，单表设计。

**Schema**:
```sql
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单用户，固定 id=1
    preferences TEXT NOT NULL DEFAULT '{}',  -- JSON dict
    constraints TEXT NOT NULL DEFAULT '[]',  -- JSON list
    tech_stack TEXT NOT NULL DEFAULT '[]',   -- JSON list
    risk_tolerance TEXT NOT NULL DEFAULT 'moderate',
    style TEXT NOT NULL DEFAULT 'concise',
    avoidance_hints TEXT NOT NULL DEFAULT '[]', -- JSON list
    updated_at TEXT NOT NULL
);
```

**理由**: SQLite 是零配置的关系型存储，支持原子写入、事务、查询。相比 JSON 文件，SQLite 提供更好的并发安全和结构化查询。单用户场景下单表单行即可。

**注入方式**: 每次 PromptBuilder.build() 时，ProfileMemory 返回结构化文本，注入 MemorySegment。格式简洁（约 200-500 tokens），无需压缩。

### D4: RetrievalMemory 双子层设计

**Episodic 子层**:
- 存储内容：任务意图、步骤摘要、结果、成功/失败、关键决策、用户反馈
- Metadata: `{"layer": "episodic", "task_type": str, "success": bool, "timestamp": str}`
- 写入时机：任务完成后、reflection 后

**Semantic 子层**:
- 存储内容：抽象规则、经验性知识、总结规律（如"该项目的测试文件都在 tests/ 目录下"）
- Metadata: `{"layer": "semantic", "category": str, "confidence": float}`
- 写入时机：用户显式指令、Agent 反思总结

**检索流程**:
```
用户输入 → 生成 query embedding
  → 向量检索 top_k 条目
  → 按 metadata.layer 过滤（可指定只搜 episodic 或 semantic）
  → 计算 relevance score
  → 截断至 max_inject_tokens
  → 注入 MemorySegment 的 retrieval 部分
```

**Token 管理**: `max_inject_tokens` 参数（默认 1500），限制注入的检索结果总量。按 relevance 排序后从高到低填充，超出截断。

### D5: ArchiveMemory 存储——JSONL

**选择**: 每次会话生成一个 JSONL 文件，每个操作记录为一行 JSON。

**格式**:
```json
{"type": "message", "role": "user", "content": "...", "tokens": 42, "ts": "2026-05-11T10:00:00Z"}
{"type": "tool_call", "tool": "search", "args": {...}, "result": "...", "ts": "..."}
{"type": "llm_request", "model": "...", "prompt_tokens": 1000, "completion_tokens": 200, "ts": "..."}
{"type": "llm_response", "content": "...", "ts": "..."}
```

**存储路径**: `.open_agent/memory/archive/{session_id}.jsonl`

**理由**: JSONL 是 append-only 格式，写入高效，天然支持流式记录。每行独立可解析，便于 replay 和 eval。无需数据库开销。

**不参与推理**: ArchiveMemory 仅实现 `write` 和 `query_for_debug` 接口，不参与 PromptBuilder 组装。

### D6: 存储目录结构

```
.open_agent/memory/
├── runtime/                  # RuntimeMemory（session 级，进程退出可丢弃）
│   └── {session_id}/         # 可选：用于断点恢复
│       ├── messages.json     # 当前对话缓冲
│       └── task_state.json   # 当前任务状态
├── profile/
│   └── profile.sqlite        # ProfileMemory 持久化
├── retrieval/
│   ├── vectors.npz           # 向量数据
│   ├── metadata.json         # 向量对应的 metadata
│   └── texts.json            # 原始文本
└── archive/
    └── {session_id}.jsonl    # 冷存储日志
```

### D7: MemoryFactory 重构

```python
class MemoryFactory:
    def create_runtime_memory(self, token_budget: int) -> RuntimeMemory
    def create_profile_memory(self, db_path: str) -> ProfileMemory
    def create_retrieval_memory(self, store_dir: str, embed_dim: int) -> RetrievalMemory
    def create_archive_memory(self, archive_dir: str, session_id: str) -> ArchiveMemory
```

所有 memory 层通过 MemoryFactory 创建，由 AgentRuntime 统一管理生命周期。

## Risks / Trade-offs

- **[向量质量]** 自实现的 numpy 向量检索依赖 embedding 质量。若使用随机投影或简单 hash，检索质量可能不佳 → 优先使用 sentence-transformers 的预训练模型生成 embedding；若无 GPU 则回退到简单 TF-IDF 向量化
- **[压缩信息丢失]** Rolling summary 压缩早期对话时，细节可能丢失 → 保留 Archive 层的完整记录作为兜底；summary 保留关键意图和结果，丢弃细节交互
- **[SQLite 并发]** SQLite 在多进程写入时可能锁冲突 → 当前单用户单进程场景无问题；如需多进程可启用 WAL 模式
- **[Embedding 模型依赖]** sentence-transformers 需要下载模型 → 首次使用时 lazy download；提供 fallback 到 TF-IDF
- **[Breaking Change]** RuntimeMemory 替换 WorkingMemory + _conversation_history 是 breaking change → 保持 MemoryManager 基类接口兼容，提供过渡期
