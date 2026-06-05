# 06: Read-Only Tool Result Caching

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Add an LRU cache in `RuntimeMemory` for read-only tool results. `ToolRegistry.execute` checks this cache before running the middleware chain for `read_only` tools. On successful execution, the result is stored in the cache. Cache keys are `(tool_name, frozen_params)`.

## Acceptance criteria

- [ ] `RuntimeMemory` has an LRU cache for read-only tool results
- [ ] `ToolRegistry.execute` checks cache before middleware chain for `read_only=True` tools
- [ ] Cache is populated on successful execution of read-only tools
- [ ] Test: second call to same read-only tool with same params returns cached result
- [ ] Test: non-read-only tools are never cached
- [ ] Test: cache key correctly differentiates different parameter sets

## User stories covered

- US 9: Repeated identical read-only tool calls avoid redundant execution

## Blocked by

- Plan 05: Output Validation Always Runs (validation must run before caching is added)
