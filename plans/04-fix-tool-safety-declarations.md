# 04: Fix Tool Safety Declarations — Remove Misleading safety_checks

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Remove the `safety_checks` declaration from `SelfTool` (no middleware handles its declared type). Change `MCPClientTool`'s `safety_checks` from `["command"]` to `["url"]` so that MCP server URLs — not startup commands — are correctly flagged for safety review.

## Acceptance criteria

- [ ] `SelfTool` no longer declares `safety_checks` that no middleware handles
- [ ] `MCPClientTool.safety_checks` is `["url"]` instead of `["command"]`
- [ ] Test: SelfTool passes through safety middleware without false positive
- [ ] Test: MCPClientTool URL safety check fires correctly, no false positive on startup commands

## User stories covered

- US 6: SelfTool doesn't declare unhandled safety_checks type
- US 7: MCPClientTool flags URLs, not shell commands

## Blocked by

None — can start immediately
