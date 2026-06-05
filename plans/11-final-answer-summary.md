# 11: Final Answer Summary

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

After the ReAct loop completes all tool steps, make a single summary LLM call with all step thought/action/observation summaries. Use short `max_tokens` (256) to control cost. The summary replaces raw tool output as the final answer returned to the user.

## Acceptance criteria

- [ ] After ReAct loop exits, a summary LLM call is made with step summaries
- [ ] Summary uses `max_tokens=256` to control cost
- [ ] Summary replaces raw tool output as final answer
- [ ] Test: agent returns human-readable summary after tool execution
- [ ] Test: summary is concise (not raw tool output dump)
- [ ] Test: loop with no tool calls still returns valid response

## User stories covered

- US 15: End user receives clear final answer instead of raw tool output

## Blocked by

None — can start immediately
