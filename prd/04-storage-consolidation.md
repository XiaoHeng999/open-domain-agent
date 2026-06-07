# PRD: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## Problem Statement

`.open_agent/` 目录下积累了 **382 个文件**（2.4 MB），文件碎片化严重：

- `eval_results/` — **93 个微小 JSON 文件**（每个仅 ~180 字节），每次 eval 运行就新增一个 `{suite}_{timestamp}.json`，历史运行无清理机制
- `checkpoints/` — **135 个 JSON 文件**（1.4 MB），每个 agent step 产生一个 `{uuid}.json`，无上限增长
- `traces/` — 每个 trace 一个 JSON 文件，随着使用量增长会继续累积
- `eval_results/trajectories/` — 每个 scenario 一个 JSON 文件，虽然目前为空，但一旦启用会产生大量碎片

与之对比，`memory/archive/` 已经采用 JSONL 追加写入模式，仅 148 个文件（按 session 分组），是合理的存储方式。

文件碎片化带来的具体问题：
1. **inode 压力** — 长期运行的 agent 环境可能耗尽 inode
2. **目录扫描变慢** — `load_eval_results()` 需要 glob + 排序 93 个文件只取最新 2 个
3. **清理困难** — 没有自动 retention 机制，只能手动删除
4. **备份/传输低效** — 大量小文件的备份和传输效率远低于少量大文件

## Solution

将追加型数据统一改为 **JSONL（JSON Lines）追加写入**，将 checkpoint 切换到 **已有的 SQLite 后端**，并增加可配置的 **retention（保留条数）** 机制。

核心思路：
- **eval_results**: 每个 suite 一个 `smoke.jsonl`，每次 eval 追加一行，保留最近 N 条
- **eval trajectories**: 每个 suite 一个 `smoke_trajectories.jsonl`，追加写入
- **checkpoints**: 默认后端从 JSON 切换到 SQLite（`SQLiteStorage` 已实现，无需新代码）
- **traces**: 统一写入 `traces.jsonl`，替换每个 trace 一个文件的模式

所有变更均保留 **向后兼容**：旧的 JSON 文件仍可被读取，平滑迁移无需一次性清理。

## User Stories

1. 作为开发者，我希望 `agent eval --suite smoke` 不再每次创建新文件，而是追加到已有 JSONL 中，这样 `.open_agent/` 目录不会无限膨胀
2. 作为开发者，我希望 eval 历史结果自动保留最近 100 条并清理更早的记录，这样我不需要手动清理旧结果
3. 作为开发者，我希望 `agent eval-trend` 能从 JSONL 中快速读取最新两次结果，而不是扫描 93 个文件排序取前 2
4. 作为开发者，我希望 eval trajectory 按套件追加到一个 JSONL 文件，而不是每个 scenario 一个独立 JSON
5. 作为开发者，我希望通过 `--trace-id` 从 JSONL 中提取特定轨迹用于离线回放，这样我不需要记住文件路径
6. 作为运维人员，我希望 checkpoint 默认使用 SQLite 存储而不是散落的 JSON 文件，这样 135 个文件变成 1 个数据库文件
7. 作为运维人员，我希望 checkpoint 的 SQLite 连接在 `on_stop()` 时正确关闭，避免 WAL 锁残留
8. 作为开发者，我希望 `agent trace <id>` 能从 JSONL 格式中加载 trace，而不是依赖单文件路径
9. 作为开发者，我希望 traces 自动保留最近 100 条，超出后自动清理最旧的记录
10. 作为开发者，我希望 retention 条数可通过配置文件和环境变量覆盖，这样不同环境可以有不同策略
11. 作为开发者，我希望旧的 JSON 格式文件仍能被正常读取，这样迁移过程不会丢失历史数据
12. 作为开发者，我希望 `list_persisted_traces()` 同时返回 JSONL 和旧 JSON 文件中的 trace ID，确保迁移后所有数据仍可发现
13. 作为 CI 管理员，我希望 eval 结果 JSONL 的 retention 可以设为较大值（如 500），这样 CI 的长期趋势分析有足够数据
14. 作为开发者，我希望 storage consolidation 不影响任何现有测试，这样我可以放心升级
15. 作为开发者，我希望 `runtime.py` 不再硬编码 `JSONStorage`，而是通过 config 让 `_build_storage()` 自动选择后端

## Implementation Decisions

### 1. 新增 `EvalConfig` 配置模型

在 `AgentConfig` 中新增 `EvalConfig` 子配置，包含 `results_retention`（默认 100）和 `trajectories_retention`（默认 200）。与 `TraceConfig`、`CheckpointConfig` 同级，遵循项目已有的 config 分层模式。

### 2. eval_results 写入改为 JSONL 追加

`EvalRunner._save_results()` 不再创建 `{suite}_{timestamp}.json`，改为以 append 模式写入 `{suite}.jsonl`。每行是一个紧凑 JSON（无缩进），包含完整的 report 对象。写入后调用 `_enforce_retention()` 检查行数是否超限。

### 3. eval trajectories 写入改为 JSONL 追加

`EvalRunner._save_trajectories()` 不再创建 `trajectories/{name}_{trace_id}.json` 子目录结构，改为写入 `{suite}_trajectories.jsonl`。每行包含 `{name, trace_id, trace}` 完整轨迹数据。

### 4. eval trend 读取兼容新旧格式

`load_eval_results()` 优先尝试读取 `{suite}.jsonl`（逐行解析，按 timestamp 降序排列，取最新 N 条）。如果 JSONL 不存在，回退到旧的 `glob({suite}_*.json)` 逻辑。这确保迁移期间新旧数据都能被读取。

### 5. eval-replay CLI 增加 `--trace-id` 选项

保留现有 `--trajectory`（直接文件路径）作为兼容。新增 `--trace-id` 选项，从 `{suite}_trajectories.jsonl` 中按 trace_id 查找并提取轨迹。

### 6. Checkpoint 默认后端切换为 SQLite

`CheckpointConfig.storage_backend` 默认值从 `"json"` 改为 `"sqlite"`。`CheckpointConfig.storage_path` 默认值从 `".open_agent/checkpoints"` 改为 `".open_agent/checkpoints/checkpoints.sqlite"`。

`SQLiteStorage` 已在 `checkpoint/storage.py` 中完整实现，无需新代码。`CheckpointManager._build_storage()` 已有分支逻辑根据 config 选择后端。

### 7. runtime.py 移除硬编码 JSONStorage

`runtime.py` 的 `on_start()` 中当前硬编码 `from ... import JSONStorage; storage = JSONStorage(...)` 并传给 `CheckpointManager`。改为直接 `CheckpointManager(config=self.config.checkpoint)`，让 `_build_storage()` 根据 config 自动选择后端。

### 8. Checkpoint on_stop 关闭 SQLite 连接

在 `AgentRuntime.on_stop()` 中，如果 `checkpoint_manager` 存在且其 `_storage` 有 `close()` 方法（即 `SQLiteStorage`），调用 `close()` 确保连接正确释放。

### 9. TraceConfig 增加 trace_retention 配置

在 `TraceConfig` 中新增 `trace_retention: int = Field(default=100, ge=1)` 字段。

### 10. Trace 持久化改为 JSONL 追加

`TraceManager.persist_trace()` 不再写入 `{trace_dir}/{trace_id}.json`，改为 append 到 `{trace_dir}/traces.jsonl`。`persist_all_traces()` 完成后调用 `_enforce_trace_retention()` 清理。

### 11. Trace 加载兼容新旧格式

`TraceManager.load_trace()` 提取 `_parse_trace_dict()` 静态方法复用解析逻辑。优先扫描 `traces.jsonl` 逐行匹配 trace_id。回退到旧的 `{trace_id}.json` 单文件。

### 12. list_persisted_traces 合并 JSONL 和旧文件

从 `traces.jsonl` 提取所有 trace_id，同时 glob 旧 `*.json` 文件的 stem，合并去重后返回。

### 13. trace CLI 命令改用 TraceManager

`agent trace <id>` 命令不再直接 `json.loads(path.read_text())`，改为通过 `TraceManager(trace_dir).load_trace(trace_id)` 统一入口，自动处理 JSONL/旧格式。

## Testing Decisions

### 测试策略：外部行为验证，不依赖内部存储格式

测试应验证以下外部行为，而非内部 JSONL 格式细节：
- 写入后能通过公开 API 读回完整数据（roundtrip）
- retention 生效后，旧数据被清理、最新数据保留
- 向后兼容：旧格式文件仍可正常加载
- CLI 命令在新旧格式下均正常工作

### 测试模块和现有先例

| 模块 | 测试文件 | 先例参考 |
|------|---------|----------|
| eval_results JSONL | `tests/test_eval_persistence.py` | 已有 JSON roundtrip 测试，改为验证 JSONL |
| eval trend | `tests/test_eval_trend.py` | 已有 fixture 写入 JSON 文件，改为写 JSONL |
| eval runner | `tests/test_eval_runner.py` | 已有 suite 运行测试 |
| checkpoint SQLite | `tests/test_checkpoint.py` | 已有 `TestStorageBackendCreation` |
| checkpoint 集成 | `tests/test_checkpoint_integration.py` | 需显式设 `storage_backend="json"` 保持现有测试 |
| trace JSONL | `tests/test_trace_persistence.py` | 已有 JSON roundtrip 测试 |
| CLI trace | 现有 CLI 测试通过 CliRunner mock | 无需新文件 |

### 关键测试用例

1. **eval JSONL roundtrip**: 写入 → `load_eval_results()` 读回，验证数据完整
2. **eval retention**: 写入 150 条 → 验证仅保留最新 100 条
3. **eval 旧格式兼容**: 创建旧 `{suite}_*.json` 文件 → `load_eval_results()` 仍能读取
4. **checkpoint SQLite 默认**: 不指定 backend → 验证使用 SQLiteStorage
5. **checkpoint 旧 JSON 兼容**: 显式 `storage_backend="json"` → 验证仍正常工作
6. **trace JSONL roundtrip**: `persist_trace()` → `load_trace()` → 验证 spans 完整
7. **trace 旧格式兼容**: 创建旧 `{trace_id}.json` → `load_trace()` 能读回
8. **trace retention**: 写入 150 个 trace → 验证 JSONL 行数 <= 100
9. **CLI trace 命令**: JSONL 中存在 trace → `agent trace <id>` 正常输出

## Out of Scope

1. **memory/archive 重构** — 已经是 JSONL 格式，无需变更
2. **memory/profile 迁移** — 已经是 SQLite，无需变更
3. **memory/retrieval 重构** — 使用 NPZ + JSON 组合，有向量检索需求，不适合 JSONL
4. **历史 JSON 文件自动迁移** — 保留向后兼容读取即可，不做自动迁移工具
5. **JSONL 并发写入锁** — eval 和 trace 通常是单进程执行，不加文件锁。未来如有需求可加 `fcntl.flock()`
6. **JSONL 压缩** — 当前数据量不大（2.4 MB），不做 gzip 压缩
7. **JSONL 文件轮转（按时间）** — 使用按条数 retention，不做按天/按周的日志轮转
8. **EvalDataset 版本存储** — `eval/dataset.py` 的 `v_{version}.json` 不在此次范围内

## Further Notes

### 实施顺序

推荐 B → A → C 的顺序，复杂度递增：

1. **Phase B (checkpoints)** — 最简单，改默认值 + 移除硬编码，3 个文件
2. **Phase A (eval_results)** — 中等，JSONL 追加 + 读取改造，5-6 个文件
3. **Phase C (traces)** — 中等，JSONL 追加 + 读取改造，4-5 个文件

每个 Phase 完成后运行 `pytest tests/ -x -q` 确认无回归。

### 文件数量预期变化

| 目录 | 变更前 | 变更后 | 减少 |
|------|--------|--------|------|
| `eval_results/` | 93 files | ~2-4 files (per-suite JSONL) | ~96% |
| `eval_results/trajectories/` | N files | ~2-4 files (per-suite JSONL) | ~95% |
| `checkpoints/` | 135 files | 1 SQLite file | ~99% |
| `traces/` | N files | 1 JSONL file | ~99% |
| **总计** | **382** | **~10** | **~97%** |

### 向后兼容策略

所有读取路径（`load_eval_results()`、`load_trace()`、`list_persisted_traces()`）均采用 "JSONL 优先，旧格式回退" 策略。这意味着：
- 现有 `.open_agent/` 中的 JSON 文件不需要手动清理
- 新数据写入 JSONL，旧数据仍可被读取
- 随着时间推移，旧 JSON 文件可以安全删除
