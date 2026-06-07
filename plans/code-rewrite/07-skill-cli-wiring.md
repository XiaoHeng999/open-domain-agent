# 07: Skill CLI Wiring

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix the `agent skill list` CLI command which always displays "(no skills loaded)" regardless of actual skill availability. The skill system (`SkillRegistry`, `scan_builtin_skills`) is fully implemented in the runtime but the CLI command never invokes it.

Wire the CLI command to create a `SkillRegistry`, call `scan_builtin_skills()` to load built-in skills, then iterate the registry to display each skill's name, description, and source directory in a Rich table.

## Acceptance criteria

- [ ] `agent skill list` command creates a `SkillRegistry` and loads built-in skills
- [ ] Output table shows skill name, description, and source for each loaded skill
- [ ] When no skills are found, shows a meaningful message (not hardcoded "(no skills loaded)")
- [ ] Existing skill tests pass (`test_skills.py`, `test_skill_extensions.py`)

## User stories covered

- US 9: `agent skill list` shows actually available skills

## Blocked by

None — can start immediately
