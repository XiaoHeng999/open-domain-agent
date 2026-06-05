# memory/ — 4 层记忆架构

- `runtime.py` — RuntimeMemory：会话级上下文窗口，滚动摘要压缩，工具结果 LRU 缓存
- `profile.py` — ProfileMemory：SQLite 用户偏好、约束、回避提示
- `retrieval.py` — RetrievalMemory：向量检索（episodic + semantic），numpy + sentence-transformers
- `archive.py` — ArchiveMemory：JSONL 冷存储，append-only
- `factory.py` — MemoryFactory：统一创建 4 层实例
- `models.py` — Message / TaskState 数据模型
- `token_utils.py` — Token 估算工具
