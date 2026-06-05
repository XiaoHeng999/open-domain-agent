# PRD-05: Fast Path 优化 — Issue Index

## Phase 1: 核心实现（无依赖）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Fast Path 核心分支](01-core-fast-path-branch.md) | AFK | — | US 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12 |

## Phase 2: 可观测性（依赖 Phase 1）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 02 | [Fast Path Trace Span](02-fast-path-trace-span.md) | AFK | 01 | US 5 |

## Phase 3: 测试覆盖（依赖 Phase 1, 2）

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 03 | [Fast Path 测试](03-fast-path-tests.md) | AFK | 01, 02 | All US verification |

## Dependency Graph

```
Phase 1 (no deps):
  01

Phase 2 (with deps):
  02 ← 01

Phase 3 (with deps):
  03 ← 01, 02
```

## Suggested Execution Order

1. Start with: 01（核心分支）
2. After 01: 02（trace span，可与 03 并行准备）
3. After 01 + 02: 03（测试覆盖）

## Architecture Boundary

| Layer | Role | Issues |
|-------|------|--------|
| Runtime | fast path 条件判断 + LLM 调用 | 01 |
| Trace | 轻量 span 可观测性 | 02 |
| Tests | 行为验证 + 回归保护 | 03 |
