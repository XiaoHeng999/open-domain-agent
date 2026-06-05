## Parent

PRD-04: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## What to build

将 eval trajectories 的写入改为 JSONL 追加，并更新 `eval-replay` CLI 命令支持从 JSONL 中按 trace_id 提取轨迹。写入侧：`_save_trajectories()` 从创建 `trajectories/{name}_{trace_id}.json` 改为追加到 `{suite}_trajectories.jsonl`，每行包含 `{name, trace_id, trace}` 完整数据。CLI 侧：`agent eval-replay` 新增 `--trace-id` 选项，从 JSONL 中查找指定轨迹；保留 `--trajectory` 直接文件路径选项作为兼容。

完成后效果：eval 轨迹不再产生大量碎片文件。开发者可通过 `agent eval-replay --trace-id abc123 --scenario evals/smoke/01_simple_qa.yaml` 快速回放，无需记住文件路径。

## Acceptance criteria

- [ ] `_save_trajectories()` 以 append 模式写入 `{suite}_trajectories.jsonl`，每行紧凑 JSON
- [ ] trajectory JSONL 应用 `EvalConfig.trajectories_retention` 保留限制
- [ ] `_save_trajectories()` 接收 `suite_name` 参数以确定输出文件名
- [ ] `agent eval-replay` 新增 `--trace-id` 选项，从 `{suite}_trajectories.jsonl` 中按 trace_id 查找轨迹
- [ ] `agent eval-replay --trajectory <path>` 仍可直接指定文件（向后兼容）
- [ ] 新增 `extract_trajectory_from_jsonl(jsonl_path, trace_id)` 辅助函数
- [ ] 测试：trajectory JSONL roundtrip（写入 → 按 trace_id 提取 → 验证数据完整）
- [ ] 测试：trajectory retention 生效
- [ ] 现有测试全部通过

## Blocked by

- 03-eval-results-jsonl（依赖 JSONL 写入基础设施和 `_enforce_retention` 模式）

## User Stories

US 4, 5
