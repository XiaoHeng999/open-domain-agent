# 14: Async CLI Input

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Replace blocking `input()` in chat mode with `prompt_toolkit` async input so that the event loop remains responsive during streaming and cancellation. This is a prerequisite for both streaming output and task cancellation.

## Acceptance criteria

- [ ] Chat mode uses `prompt_toolkit` (or similar) for async input instead of blocking `input()`
- [ ] Event loop remains responsive while waiting for user input
- [ ] Existing chat mode functionality preserved (multi-line, history)
- [ ] Test: async input does not block event loop
- [ ] Test: chat mode interactive session works correctly

## User stories covered

- US 29: Async input keeps event loop responsive during streaming and cancellation

## Blocked by

None — can start immediately
