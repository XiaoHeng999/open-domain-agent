# 09: Provider Hardening — Temperature + Retry

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Pass `temperature` in all Anthropic provider API calls (`complete`, `complete_with_tools`). Wrap all provider API calls with `tenacity.retry` targeting transient HTTP errors (429, 502, 503, connection timeouts) — max 3 retries, exponential backoff (1s, 2s, 4s).

## Acceptance criteria

- [ ] Anthropic `complete` passes `temperature` parameter
- [ ] Anthropic `complete_with_tools` passes `temperature` parameter
- [ ] All provider API calls wrapped with tenacity retry (429, 502, 503, timeout)
- [ ] Retry: max 3 attempts, exponential backoff (1s, 2s, 4s)
- [ ] Test: Anthropic provider receives temperature in API call kwargs
- [ ] Test: 429 response triggers retry and eventually succeeds
- [ ] Test: 503 response triggers retry
- [ ] Test: non-transient errors (400, 401) are not retried

## User stories covered

- US 12: Anthropic provider passes temperature to all API calls
- US 13: Transient API errors retry with exponential backoff

## Blocked by

None — can start immediately
