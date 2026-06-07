# PRD-06: Codebase Health — Issue Index

## Phase P0: Critical Fixes

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Ghost Exports & Naming Collision Fixes](01-ghost-exports-and-naming-fixes.md) | AFK | — | US 4, 5 |
| 02 | [Sandbox Async & Lifecycle Fix](02-sandbox-async-and-lifecycle-fix.md) | AFK | — | US 6, 17 |

## Phase P1: Feature Fixes & Code Quality

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 03 | [Memory Tracing Wiring](03-memory-tracing-wiring.md) | AFK | — | US 7 |
| 04 | [complete_structured → complete_with_tools Migration](04-complete-structured-migration.md) | AFK | — | US 14 |
| 05 | [Output Validation Empty Output Fix](05-output-validation-empty-output-fix.md) | AFK | — | US 8 |
| 06 | [SQLite Concurrency & Encapsulation Fix](06-sqlite-concurrency-and-encapsulation.md) | AFK | — | US 11, 16 |
| 07 | [Skill CLI Wiring](07-skill-cli-wiring.md) | AFK | — | US 9 |
| 08 | [Recovery Strategy Dead Paths Cleanup](08-recovery-dead-paths-cleanup.md) | AFK | — | US 10 |
| 09 | [Silent Exception Tiered Logging](09-silent-exception-tiered-logging.md) | AFK | — | US 15 |
| 10 | [Dead Code & Duplicate Implementation Cleanup](10-dead-code-and-duplicate-cleanup.md) | AFK | 01-09 | US 12, 13 |
| 11 | [CLI Token Usage Real-Time Display](11-cli-token-usage-display.md) | AFK | — | US 1, 2, 3 |
| 12 | [Docs & Deprecation Marker Updates](12-docs-and-deprecation-updates.md) | AFK | — | US 18, 19 |

## Phase P2: Test Infrastructure

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 13 | [Test Infrastructure](13-test-infrastructure.md) | AFK | 01-10 | US 20, 21, 22 |

## Dependency Graph

```
P0 (no deps — start here):
  01, 02

P1 (no deps — can run in parallel with P0):
  03, 04, 05, 06, 07, 08, 09, 11, 12

P1 (blocked — run last in P1):
  10 ← 01-09

P2 (blocked — run after all P1):
  13 ← 01-10
```

## Suggested Execution Order

1. P0 batch: 01, 02 (parallel)
2. P1 batch 1: 03, 04, 05, 06, 07, 08, 09, 11, 12 (parallel)
3. After 01-09 complete: 10 (dead code cleanup — touches many files)
4. After 01-10 complete: 13 (test infrastructure)
