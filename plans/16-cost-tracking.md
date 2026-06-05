# 16: Cost Tracking

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Add `usage: dict[str, int] | None` field to `ToolCallResponse`. Each provider extracts usage from raw API responses. A `CostTracker` class accumulates per-model, per-day usage with configurable pricing. Exposes `get_daily_summary()`, `get_weekly_summary()`, `check_budget(limit)`. Integrated into `AgentRuntime.run` to record usage after each iteration.

## Acceptance criteria

- [ ] `ToolCallResponse` has `usage` field (input_tokens, output_tokens)
- [ ] OpenAI provider extracts usage from API response
- [ ] Anthropic provider extracts usage from API response
- [ ] `CostTracker` accumulates per-model, per-day token usage
- [ ] `CostTracker.get_daily_summary()` and `get_weekly_summary()` return correct aggregations
- [ ] `CostTracker.check_budget(limit)` returns over/under status
- [ ] `AgentConfig` has `cost_tracking.enabled` and `cost_tracking.budget_daily` fields
- [ ] Test: usage extracted from provider responses correctly
- [ ] Test: CostTracker aggregates across multiple requests
- [ ] Test: budget alert fires when limit exceeded

## User stories covered

- US 21: Per-request token usage recorded from API responses
- US 22: CostTracker with summaries and budget alerts

## Blocked by

- Plan 09: Provider Hardening (touches same provider code for response handling)
