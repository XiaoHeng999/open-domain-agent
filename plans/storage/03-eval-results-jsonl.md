## Parent

PRD-04: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## What to build

将 eval_results 的写入和读取全面改为 JSONL 格式。写入侧：`EvalRunner._save_results()` 从每次创建一个 `{suite}_{timestamp}.json` 改为追加到 `{suite}.jsonl`，写入后按 `EvalConfig.results_retention` 自动清理超限行。读取侧：`load_eval_results()` 优先从 JSONL 读取（按 timestamp 降序取最新 N 条），回退到旧的 glob 单文件逻辑保证向后兼容。

完成后效果：`agent eval --suite smoke` 不再每次新增文件，而是追加到 `smoke.jsonl`。`agent eval-trend` 从 JSONL 快速读取最新两次结果。旧的 `{suite}_*.json` 文件仍可被正常读取。

## Acceptance criteria

- [ ] `_save_results()` 以 append 模式写入 `.open_agent/eval_results/{suite}.jsonl`，每行紧凑 JSON
- [ ] 新增 `_enforce_retention(path, max_retention)` 方法：行数超限时重写保留末尾 N 行
- [ ] retention 值来自 `EvalConfig.results_retention`（默认 100）
- [ ] `load_eval_results()` 优先读取 `{suite}.jsonl`（逐行解析，按 timestamp 降序，取 latest N）
- [ ] `load_eval_results()` 在 JSONL 不存在时回退到旧的 `glob({suite}_*.json)` 逻辑
- [ ] 写入 150 条后验证 JSONL 仅保留最新 100 条（retention 测试）
- [ ] 创建旧格式 `{suite}_*.json` 文件后，`load_eval_results()` 仍能正常读取（向后兼容测试）
- [ ] JSONL roundtrip：写入 → 读回，验证数据完整（suite name、timestamp、results、metrics、summary）
- [ ] 现有 `test_eval_persistence.py` 和 `test_eval_trend.py` 测试更新并全部通过

## Blocked by

- 02-config-retention-foundation（需要 `EvalConfig.results_retention`）

## User Stories

US 1, 2, 3, 11
