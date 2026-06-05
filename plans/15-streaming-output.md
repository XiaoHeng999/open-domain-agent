# 15: Streaming Output

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Add `stream=True` support to provider `complete_with_tools`, yielding partial text chunks. ReActLoop streams thought text to a callback/emitter as it arrives. Long-running tools (exec, web fetch) emit progress via an `on_progress` callback. CLI displays real-time output.

## Acceptance criteria

- [ ] Provider `complete_with_tools` supports `stream=True`, yielding text chunks
- [ ] ReActLoop streams thought text via callback as LLM generates it
- [ ] Long-running tools emit progress via `on_progress` callback
- [ ] CLI displays streaming output in real-time
- [ ] Test: streaming callback receives text chunks in order
- [ ] Test: tool progress callback fires during long execution
- [ ] Test: non-streaming mode still works correctly

## User stories covered

- US 19: LLM thinking streams in real-time during ReAct loop
- US 20: Long-running tools show intermediate progress

## Blocked by

- Plan 08: RuntimeMemory Manages Tool Messages (avoid merge conflicts in ReActLoop)
- Plan 14: Async CLI Input (event loop must be responsive for streaming display)
