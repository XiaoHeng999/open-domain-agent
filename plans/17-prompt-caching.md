# 17: Prompt Caching

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Add `cache_control: {"type": "ephemeral"}` markers to system prompts and tool definitions in the Anthropic provider. Add `caching: bool = True` config option to `AgentConfig`. Only apply when `caching=True` and provider is Anthropic.

## Acceptance criteria

- [ ] `AgentConfig` has `caching: bool = True` field
- [ ] Anthropic provider adds `cache_control` markers to system message
- [ ] Anthropic provider adds `cache_control` markers to tool definitions
- [ ] Markers only applied when `caching=True` and provider is Anthropic
- [ ] Test: Anthropic requests include `cache_control` markers when enabled
- [ ] Test: no markers when `caching=False`
- [ ] Test: no markers for non-Anthropic providers

## User stories covered

- US 23: Anthropic provider marks system prompts and tools with cache_control
- US 24: Config option toggles prompt caching

## Blocked by

- Plan 09: Provider Hardening (touches same Anthropic provider code)
