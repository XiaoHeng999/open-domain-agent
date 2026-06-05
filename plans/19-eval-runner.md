# 19: Eval Runner + CLI Command

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Build a minimal eval runner that loads YAML test scenarios (`name`, `input`, `expected_tools`, `expected_outcome`) and executes them against `AgentRuntime`. Add CLI command `agent eval --suite smoke` to invoke the runner and display pass/fail results.

## Acceptance criteria

- [ ] YAML scenario format: `name`, `input`, `expected_tools` (optional), `expected_outcome` (optional)
- [ ] `EvalRunner` loads scenarios from configurable directory
- [ ] `EvalRunner` executes scenarios against `AgentRuntime`
- [ ] CLI `agent eval --suite smoke` runs scenarios and displays pass/fail
- [ ] Test: YAML scenario loads and parses correctly
- [ ] Test: eval runner reports pass for matching scenario
- [ ] Test: eval runner reports fail for mismatched scenario

## User stories covered

- US 27: Eval runner loads YAML scenarios and executes against AgentRuntime
- US 28: CLI `agent eval` command runs evals and displays results

## Blocked by

None — can start immediately
