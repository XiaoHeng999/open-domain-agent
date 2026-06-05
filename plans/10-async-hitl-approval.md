# 10: Async HITL Approval

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening

## What to build

Change `HITLApprovalManager.approve` from `def` to `async def` so that interactive user approval does not block the asyncio event loop. Update all callers (`PermissionMiddleware`, `PermissionGuard`) to `await` the call.

## Acceptance criteria

- [ ] `HITLApprovalManager.approve` is `async def approve(...) -> ApprovalResult`
- [ ] `PermissionMiddleware` calls `await approve(...)` instead of synchronous call
- [ ] `PermissionGuard` calls `await approve(...)` instead of synchronous call
- [ ] Test: async approve works correctly with await
- [ ] Test: existing permission integration tests pass

## User stories covered

- US 14: HITL approval is async, doesn't block event loop

## Blocked by

None — can start immediately
