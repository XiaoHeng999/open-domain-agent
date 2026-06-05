# PRD-04: 存储层碎片化治理 — Issue Index

## Phase 1: 基础设施（无依赖，可并行）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Checkpoint 默认切换 SQLite](01-checkpoint-sqlite-default.md) | AFK | — | US 6, 7, 14, 15 |
| 02 | [存储配置基础设施 (EvalConfig + TraceConfig retention)](02-config-retention-foundation.md) | AFK | — | US 10, 13 |

## Phase 2: JSONL 写入改造（依赖 Phase 1）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 03 | [Eval results JSONL 端到端](03-eval-results-jsonl.md) | AFK | 02 | US 1, 2, 3, 11 |
| 05 | [Trace JSONL 端到端](05-trace-jsonl.md) | AFK | 02 | US 8, 9, 11, 12 |

## Phase 3: Trajectory 完善（依赖 Phase 2）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 04 | [Eval trajectories JSONL + eval-replay CLI](04-eval-trajectories-jsonl.md) | AFK | 03 | US 4, 5 |

## Dependency Graph

```
Phase 1 (no deps):
  01, 02

Phase 2 (with deps):
  03 ← 02
  05 ← 02

Phase 3 (with deps):
  04 ← 03
```

## Suggested Execution Order

1. Parallel batch 1: 01, 02（无依赖，同时开始）
2. After 02: 03, 05（并行）
3. After 03: 04

## Architecture Boundary

| Layer | Role | Issues |
|-------|------|--------|
| Config | 配置基础设施 | 02 |
| Checkpoint | 存储后端切换 | 01 |
| Eval | 评估结果存储 | 03, 04 |
| Trace | 执行追踪存储 | 05 |
