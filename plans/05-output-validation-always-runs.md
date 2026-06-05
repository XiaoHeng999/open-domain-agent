# 05: Output Validation Always Runs

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Move the `validate_output()` call in `OutputValidationMiddleware.process` outside the `if output_schema is not None` block so that semantic output validation runs for every tool execution, not just tools with a JSON schema.

## Acceptance criteria

- [ ] `OutputValidationMiddleware.process` calls `validate_output()` unconditionally (outside the schema check)
- [ ] Tools without `output_schema` still have their `validate_output()` method called
- [ ] Test: a tool with no `output_schema` but a `validate_output()` implementation has that method called during execution
- [ ] Test: existing middleware chain tests pass unchanged

## User stories covered

- US 8: `validate_output()` runs on every tool execution regardless of `output_schema`

## Blocked by

None — can start immediately
