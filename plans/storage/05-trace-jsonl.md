## Parent

PRD-04: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## What to build

将 trace 持久化从每个 trace 一个 JSON 文件改为统一追加到 `traces.jsonl`。包括：写入侧 `persist_trace()` 改为 append 模式，`persist_all_traces()` 完成后按 `TraceConfig.trace_retention` 清理；读取侧 `load_trace()` 提取 `_parse_trace_dict()` 复用解析逻辑，优先扫描 JSONL 逐行匹配 trace_id，回退到旧的单文件格式；`list_persisted_traces()` 合并 JSONL 和旧文件中的 trace ID；CLI `agent trace <id>` 改用 `TraceManager.load_trace()` 统一入口。

完成后效果：所有 trace 追加到单个 `traces.jsonl`，自动保留最近 100 条。`agent trace <id>` 能从 JSONL 中加载。旧的 `{trace_id}.json` 文件仍可被发现和读取。

## Acceptance criteria

- [ ] `persist_trace()` 以 append 模式写入 `{trace_dir}/traces.jsonl`，每行紧凑 JSON
- [ ] 新增 `_enforce_trace_retention()` 方法，按 `TraceConfig.trace_retention` 清理
- [ ] `persist_all_traces()` 完成后调用 retention 清理
- [ ] 提取 `_parse_trace_dict()` 静态方法，复用于 JSONL 和旧格式解析
- [ ] `load_trace()` 优先扫描 `traces.jsonl` 逐行匹配 trace_id，回退到旧 `{trace_id}.json`
- [ ] `list_persisted_traces()` 从 JSONL 提取 trace_id，合并旧 `*.json` 文件的 stem，去重返回
- [ ] `agent trace <id>` 改用 `TraceManager(trace_dir).load_trace(trace_id)`，不再直接读取文件
- [ ] Trace JSONL roundtrip：`persist_trace()` → `load_trace()` → 验证 spans、metadata 完整
- [ ] Trace retention：写入 150 个 trace → JSONL 行数 <= 100
- [ ] 向后兼容：创建旧格式 `{trace_id}.json` → `load_trace()` 能读回
- [ ] 向后兼容：旧 `*.json` 文件的 stem 出现在 `list_persisted_traces()` 结果中
- [ ] CLI 测试：JSONL 中存在 trace → `agent trace <id>` 正常输出
- [ ] 现有 `test_trace_persistence.py` 测试更新并全部通过

## Blocked by

- 02-config-retention-foundation（需要 `TraceConfig.trace_retention`）

## User Stories

US 8, 9, 11, 12
