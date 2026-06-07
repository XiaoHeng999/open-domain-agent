# 05: Output Validation Empty Output Fix

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix `OutputValidationMiddleware` incorrectly treating legitimate empty tool output as errors. Currently `ExecTool.validate_output()` and `ReadFileTool.validate_output()` both return error messages for empty results, but empty output is a valid outcome (e.g., `touch file && cat file`, or a command that succeeds silently).

Refine the semantics:
- **ExecTool**: Empty stdout is valid (command ran successfully, produced no output). Only non-zero exit codes or execution exceptions should be flagged as errors.
- **ReadFileTool**: An empty file is valid. Only actual read failures (file not found, permission denied) should be flagged as errors.

The validation should return an empty list (no issues) for legitimate empty results, and only return error strings for genuine failures.

## Acceptance criteria

- [ ] `ExecTool.validate_output()` returns empty list for empty-but-successful command output
- [ ] `ExecTool.validate_output()` returns error strings only for actual execution failures
- [ ] `ReadFileTool.validate_output()` returns empty list for empty file content
- [ ] `ReadFileTool.validate_output()` returns error strings only for read failures
- [ ] Middleware chain does not replace legitimate empty results with error messages
- [ ] Existing middleware tests pass (`test_middleware_chain.py`, `test_tool_filesystem.py`, `test_tool_shell.py`)

## User stories covered

- US 8: Running a command with no output is not flagged as an error

## Blocked by

None — can start immediately
