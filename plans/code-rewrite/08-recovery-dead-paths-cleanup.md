# 08: Recovery Strategy Dead Paths Cleanup

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Remove two ineffective recovery code paths that are guaranteed to produce no results:

1. **`RetrievalRecoveryStrategy._expand_query()`** — always appends `" OR *"` to the query string. This is syntactically meaningless for search engines and provides no actual query expansion. Remove the method and its call sites.

2. **`ServiceRecoveryStrategy` fallback tool lookup** — searches the tool registry for tools tagged `"fallback"`, but no tool in the codebase registers with that tag. The lookup always returns empty. Remove the fallback lookup logic.

Also add a 200-result limit to `SearchTool._glob()`, matching the pattern used by `_grep` but with a higher threshold (200 vs 50) since glob results are typically shorter.

## Acceptance criteria

- [ ] `_expand_query()` method removed from `RetrievalRecoveryStrategy`
- [ ] Call sites of `_expand_query()` updated to proceed without it
- [ ] `"fallback"` tag tool lookup removed from `ServiceRecoveryStrategy`
- [ ] `SearchTool._glob()` limits results to 200 entries with truncation notice
- [ ] Existing recovery and search tests pass (`test_recovery.py`, `test_tool_search.py`)

## User stories covered

- US 10: Recovery strategy fallback lookup actually finds tools (by removing the empty path)
- US 11: `_glob` search has result count limit

## Blocked by

None — can start immediately
