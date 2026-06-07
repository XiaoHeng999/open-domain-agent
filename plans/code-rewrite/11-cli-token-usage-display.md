# 11: CLI Token Usage Real-Time Display

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Add real-time token usage display to the CLI chat mode (`agent chat`). Three pieces of information should be visible:

1. **Per-response token count**: After each agent response, show `Tokens: ~N` indicating how many tokens the current request consumed.

2. **Session cumulative tokens**: After each response, show `Session total: ~N` with the running total of tokens used in the session.

3. **Budget indicator in prompt prefix**: Before user input, show `[budget: remaining/total]` where `remaining = runtime_token_budget - current_tokens` and `total = runtime_token_budget`.

Data sources: `RuntimeMemory._total_tokens()` for current usage, `MemoryConfig.runtime_token_budget` for the total budget. Access these via the runtime's memory instance.

## Acceptance criteria

- [ ] After each response, CLI shows token count for that response (e.g., `Tokens: ~1200`)
- [ ] After each response, CLI shows cumulative session token count (e.g., `Session total: ~5600`)
- [ ] Prompt prefix shows remaining budget (e.g., `[budget: 2400/8000]`)
- [ ] Display only appears in chat mode, not in single-run mode
- [ ] Existing CLI tests pass (`test_cli_verbose_debug.py`, `test_async_cli_input.py`)

## User stories covered

- US 1: User sees per-response token cost after each reply
- US 2: User sees cumulative session token usage
- US 3: User sees remaining token budget before typing

## Blocked by

None — can start immediately
