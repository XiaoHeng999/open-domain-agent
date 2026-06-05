# PRD-01: Bug Fixes & Harness Hardening — Issue Index

## Phase 1: Bug Fixes & Security

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Register All 4 New Tools](01-register-all-4-new-tools.md) | AFK | — | US 1, 2, 3 |
| 02 | [Harden Docker Sandbox](02-harden-docker-sandbox.md) | AFK | — | US 4 |
| 03 | [Block Symlink Traversal](03-block-symlink-traversal.md) | AFK | — | US 5 |
| 04 | [Fix Tool Safety Declarations](04-fix-tool-safety-declarations.md) | AFK | — | US 6, 7 |
| 05 | [Output Validation Always Runs](05-output-validation-always-runs.md) | AFK | — | US 8 |
| 06 | [Read-Only Tool Result Caching](06-read-only-tool-result-caching.md) | AFK | 05 | US 9 |
| 07 | [Parallel Tool Execution](07-parallel-tool-execution.md) | AFK | — | US 10 |
| 08 | [RuntimeMemory Manages Tool Messages](08-runtimememory-manages-tool-messages.md) | AFK | 07 | US 11 |
| 09 | [Provider Hardening — Temperature + Retry](09-provider-hardening.md) | AFK | — | US 12, 13 |
| 10 | [Async HITL Approval](10-async-hitl-approval.md) | AFK | — | US 14 |

## Phase 2: Harness Capabilities

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 11 | [Final Answer Summary](11-final-answer-summary.md) | AFK | — | US 15 |
| 12 | [Feedback Loop via ProfileMemory](12-feedback-loop-via-profile-memory.md) | AFK | — | US 16 |
| 13 | [Conversation Persistence with SQLite](13-conversation-persistence-sqlite.md) | AFK | — | US 17, 18 |
| 14 | [Async CLI Input](14-async-cli-input.md) | AFK | — | US 29 |
| 15 | [Streaming Output](15-streaming-output.md) | AFK | 08, 14 | US 19, 20 |
| 16 | [Cost Tracking](16-cost-tracking.md) | AFK | 09 | US 21, 22 |
| 17 | [Prompt Caching](17-prompt-caching.md) | AFK | 09 | US 23, 24 |
| 18 | [Task Cancellation with ESC Key](18-task-cancellation.md) | AFK | 14 | US 25, 26 |
| 19 | [Eval Runner + CLI Command](19-eval-runner.md) | AFK | — | US 27, 28 |

## Dependency Graph

```
Phase 1 (no deps):
  01, 02, 03, 04, 05, 07, 09, 10

Phase 1 (with deps):
  06 ← 05
  08 ← 07

Phase 2 (no deps):
  11, 12, 13, 14, 19

Phase 2 (with deps):
  15 ← 08, 14
  16 ← 09
  17 ← 09
  18 ← 14
```

## Suggested Execution Order

1. Start with security-critical: 02, 03
2. Parallel batch 1: 01, 04, 05, 07, 09, 10
3. After batch 1: 06 (after 05), 08 (after 07)
4. Phase 2 batch 1: 11, 12, 13, 14, 19
5. After 09: 16, 17
6. After 08 + 14: 15
7. After 14: 18
