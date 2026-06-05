# checkpoint/ — 状态持久化

- `manager.py` — CheckpointManager：步级保存/恢复/继续，含幂等键去重
- `storage.py` — JSONStorage / SQLiteStorage 两种后端
