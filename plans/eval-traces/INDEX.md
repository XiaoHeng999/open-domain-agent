# PRD-03: Trace & Eval 系统全面改造 — Issue Index

## Phase 1: Trace 基础设施

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Trace 持久化 + agent trace 命令](01-trace-persistence.md) | AFK | — | US 1, 2, 5 |
| 02 | [CLI --verbose/--debug 标志](02-cli-verbose-debug.md) | AFK | — | US 3, 4 |

## Phase 2: Span 覆盖补全

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 03 | [Memory 子系统可观测（MEMORY_OP spans）](03-memory-spans.md) | AFK | 01 | US 6 |
| 04 | [Recovery 可观测（RECOVERY spans）](04-recovery-spans.md) | AFK | 01 | US 7 |

## Phase 3: Eval 系统改造

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 05 | [Eval 接入 TraceReplayEngine（路径 B）](05-eval-path-b.md) | AFK | 01 | US 9, 10, 11 |
| 06 | [LLMJudge 评分修复](06-llmjudge-fix.md) | AFK | 05 | US 12 |
| 07 | [Eval 聚合指标 + Trajectory 持久化](07-metrics-trajectory.md) | AFK | 05 | US 13, 14 |
| 10 | [Eval spans 可观测（EVAL spans）](10-eval-spans.md) | AFK | 05 | US 8 |

## Phase 4: Monitoring 边界清理

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 08 | [Monitoring 边界清理](08-monitoring-cleanup.md) | AFK | 05 | US 15, 16 |

## Phase 5: CI + 趋势分析

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 09 | [CI + 趋势分析 + 离线回放](09-ci-trend-replay.md) | AFK | 05, 07 | US 17, 18, 19 |

## Dependency Graph

```
Phase 1 (no deps):
  01, 02

Phase 2 (with deps):
  03 ← 01
  04 ← 01

Phase 3 (with deps):
  05 ← 01
  06 ← 05
  07 ← 05
  10 ← 05

Phase 4 (with deps):
  08 ← 05

Phase 5 (with deps):
  09 ← 05, 07
```

## Suggested Execution Order

1. Parallel batch 1: 01, 02（无依赖，同时开始）
2. After 01: 03, 04, 05（并行）
3. After 05: 06, 07, 08, 10（并行）
4. After 05 + 07: 09

## Architecture Boundary

| Layer | Role | Issues |
|-------|------|--------|
| Trace | 纯记录层 | 01, 02, 03, 04, 10 |
| Eval | 离线评估层（唯一评分入口） | 05, 06, 07 |
| Monitoring | 实时观察层 | 08 |
| CI/Tooling | 工具链 | 09 |
