# PRD-02: Eval System Hardening + Feature Verification — Issue Index

## Phase 1: Bug Fixes

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 01 | [Fix Streaming Tool_Calls + DeepSeek URL](01-fix-streaming-toolcalls-and-deepseek-url.md) | AFK | — | US 1, 2, 3 |

## Phase 2: Eval Infrastructure

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 02 | [Create evals/smoke/ YAML Scenarios](02-create-evals-smoke-scenarios.md) | AFK | — | US 4, 5, 6 |
| 03 | [Wire CLI eval to AgentRuntime](03-wire-cli-eval-to-runtime.md) | AFK | 01 | US 7, 8 |
| 04 | [Eval Result Persistence](04-eval-result-persistence.md) | AFK | 03 | US 9, 10 |

## Phase 3: E2E Live Verification

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 05 | [E2E Live Scaffold + DeepSeek QA](05-e2e-live-test-scaffold-deepseek-qa.md) | HITL | 01 | US 11, 12 |
| 06 | [E2E ReAct + Tool Calling](06-e2e-react-tool-calling.md) | HITL | 05 | US 13 |
| 07 | [E2E Streaming + Tool Calls](07-e2e-streaming-tool-calls.md) | HITL | 01, 05 | US 14 |
| 08 | [E2E Task Cancellation](08-e2e-task-cancellation.md) | HITL | 05 | US 15 |
| 09 | [E2E Full Smoke Eval Suite](09-e2e-run-smoke-eval-suite.md) | HITL | 02, 03, 05 | US 16 |

## Phase 4: Boundary Tests

| # | Issue | Type | Blocked by | User Stories |
|---|-------|------|------------|--------------|
| 10 | [Boundary Tests — Streaming](10-boundary-tests-streaming.md) | AFK | 01 | US 17 |
| 11 | [Boundary Tests — Cancellation + ReAct + DeepSeek](11-boundary-tests-cancellation-react-deepseek.md) | AFK | 01 | US 18, 19, 20 |

## Dependency Graph

```
Phase 1 (no deps):
  01

Phase 2 (no deps):
  02

Phase 2 (with deps):
  03 ← 01
  04 ← 03

Phase 3 (with deps):
  05 ← 01
  06 ← 05
  07 ← 01, 05
  08 ← 05
  09 ← 02, 03, 05

Phase 4 (with deps):
  10 ← 01
  11 ← 01
```

## Suggested Execution Order

1. Bug fix first: 01
2. Parallel batch 1: 02 (与 01 同时开始)
3. After 01: 03, 05, 10, 11 (并行)
4. After 03: 04
5. After 05: 06, 07, 08 (并行，需要 DEEPSEEK_API_KEY)
6. After 02 + 03 + 05: 09 (需要 DEEPSEEK_API_KEY)
