## Parent

PRD-04: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## What to build

将 checkpoint 默认存储后端从 JSON（每 step 一个 JSON 文件）切换为 SQLite（单文件数据库）。`SQLiteStorage` 已经完整实现，本 issue 只需切换默认配置、移除 `runtime.py` 中硬编码的 `JSONStorage` 引用、确保 `on_stop()` 正确关闭 SQLite 连接、并修复受影响的测试。

完成后效果：新创建的 checkpoint 不再散落为大量 JSON 文件，而是写入 `.open_agent/checkpoints/checkpoints.sqlite` 单文件。现有 JSON 后端仍可通过配置显式选用。

## Acceptance criteria

- [ ] `CheckpointConfig.storage_backend` 默认值为 `"sqlite"`，`storage_path` 默认值为 `.open_agent/checkpoints/checkpoints.sqlite`
- [ ] `runtime.py` 不再硬编码 `JSONStorage`，而是通过 `CheckpointManager(config=...)` 让 `_build_storage()` 自动选择后端
- [ ] `AgentRuntime.on_stop()` 在 checkpoint_manager 的 storage 有 `close()` 方法时调用之
- [ ] 不指定任何 config 时，`CheckpointManager` 默认创建 `SQLiteStorage` 实例
- [ ] 显式设置 `storage_backend="json"` 时，仍使用 `JSONStorage`，行为不变
- [ ] 现有测试全部通过（受影响的测试显式设置 `storage_backend="json"` 保持原有行为）
- [ ] 新增测试：验证默认后端为 SQLite、验证 SQLite roundtrip、验证 on_stop 关闭连接

## Blocked by

None — can start immediately.

## User Stories

US 6, 7, 14, 15
