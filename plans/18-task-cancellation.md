# 18: Task Cancellation with ESC Key

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Create a `CancellationToken` wrapping an `asyncio.Event`. Pass it into `ReActLoop.run` and check at each iteration boundary. In CLI chat mode, ESC key press sets the event via `prompt_toolkit` key bindings. Cancellation is graceful — no state corruption.

## Acceptance criteria

- [ ] `CancellationToken` wraps `asyncio.Event` with `cancel()` and `is_cancelled`
- [ ] `ReActLoop.run` checks token at each iteration boundary and exits cleanly
- [ ] CLI chat mode: ESC key press triggers cancellation
- [ ] Cancellation does not corrupt tool state or memory
- [ ] Test: cancellation token stops loop at iteration boundary
- [ ] Test: loop state is consistent after cancellation
- [ ] Test: ESC key binding triggers cancel

## User stories covered

- US 25: ESC cancels running agent task in chat mode
- US 26: CancellationToken checked at iteration boundaries

## Blocked by

- Plan 14: Async CLI Input (ESC key binding requires async input handling)
