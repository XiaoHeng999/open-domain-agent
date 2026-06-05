# 13: Conversation Persistence with SQLite

## Type
AFK

## Parent

PRD-01: Bug Fixes & Harness Hardening — Phase 2

## What to build

Add SQLite-backed persistence to `RuntimeMemory`. When enabled via config (`persistence.enabled`), `add_message` writes to both in-memory buffer and SQLite (async via `asyncio.to_thread`). On startup, load last N messages from SQLite. Background cleanup deletes records older than 7 days (`persistence.retention_days`). Schema: `messages(id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)`.

## Acceptance criteria

- [ ] `AgentConfig` has `persistence.enabled`, `persistence.db_path`, `persistence.retention_days` fields
- [ ] `RuntimeMemory.add_message` writes to SQLite when persistence enabled
- [ ] On startup, last N messages are loaded from SQLite
- [ ] Records older than `retention_days` are auto-cleaned
- [ ] Test: message round-trip: add → restart → load from SQLite
- [ ] Test: 7-day cleanup deletes old records, keeps recent ones
- [ ] Test: with persistence disabled, no SQLite operations occur

## User stories covered

- US 17: Conversation history persists across process restarts
- US 18: Old conversation records auto-cleaned after 7 days

## Blocked by

None — can start immediately
