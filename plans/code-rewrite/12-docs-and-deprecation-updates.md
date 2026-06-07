# 12: Docs & Deprecation Marker Updates

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix two documentation/annotation inconsistencies:

1. **`QualityScorer` deprecation marker**: The class docstring says it's deprecated and moved to `eval.metrics`, but the runtime still actively instantiates and uses it for real-time quality scoring. Remove the deprecation note — `QualityScorer` (real-time) and `eval.metrics` (post-hoc) serve different purposes.

2. **`@tool_schema` docs contradiction**: `docs/adding-tools.md` says `@tool_schema` is deprecated and users should use Tool ABC inheritance instead. But sandbox modules (`daytona.py`, `docker.py`) actively use `@tool_schema` for dynamic schema registration. Update the docs to clarify: `@tool_schema` is the recommended approach for sandbox integration, while Tool ABC inheritance is for standalone tool classes.

## Acceptance criteria

- [ ] `QualityScorer` docstring no longer contains deprecation warning
- [ ] `docs/adding-tools.md` updated to clarify when to use `@tool_schema` vs Tool ABC
- [ ] No misleading deprecation markers remain

## User stories covered

- US 18: `QualityScorer` is not marked as deprecated if still in use
- US 19: Documentation about `@tool_schema` matches actual code usage

## Blocked by

None — can start immediately
