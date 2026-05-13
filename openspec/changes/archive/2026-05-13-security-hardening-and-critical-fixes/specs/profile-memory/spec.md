## MODIFIED Requirements

### Requirement: ProfileMemory Persistent Storage
Uses SQLite to persist user profile data (preferences, constraints, tech_stack, risk_tolerance, style, avoidance_hints). Single-user model with a fixed `id=1` row. All database operations MUST be protected by an `asyncio.Lock` to prevent concurrent write corruption. The lock MUST be acquired before any write or read-modify-write operation.

#### Scenario: Concurrent write operations
- **WHEN** two async tasks simultaneously call _apply_updates on the same ProfileMemory instance
- **THEN** the lock serializes the writes, no "database is locked" error occurs

#### Scenario: Read during write
- **WHEN** a read operation occurs while a write is in progress
- **THEN** the read sees either the pre-write or post-write state (no partial state)
