# 12: Feedback Loop via ProfileMemory

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Read avoidance hints from `ProfileMemory` and inject them into the system prompt via `PromptBuilder` or `_build_messages`. Hints should be specific (tool name, error pattern, suggested alternative) and persist across sessions.

## Acceptance criteria

- [ ] `PromptBuilder` (or `_build_messages`) reads avoidance hints from `ProfileMemory`
- [ ] Hints are injected into the system prompt as structured text
- [ ] Hints include tool name, error pattern, and suggested alternative
- [ ] Test: avoidance hints appear in constructed system prompt
- [ ] Test: agent with past failures has relevant hints injected

## User stories covered

- US 16: FeedbackLoop avoidance hints persist across sessions via ProfileMemory

## Blocked by

None — can start immediately
