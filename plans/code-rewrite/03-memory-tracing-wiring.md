# 03: Memory Tracing Wiring

## Type
AFK

## Parent

PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## What to build

Fix the completely non-functional memory tracing. Four memory modules (`RuntimeMemory`, `ProfileMemory`, `RetrievalMemory`, `ArchiveMemory`) each have a `_start_*_span()` helper that checks `self._trace_manager` and `self._current_trace_id`. Neither attribute is ever set on any memory instance, so every span helper returns `None` — all memory operations are invisible in traces.

Wire the attributes in the runtime's `on_start()` method: after creating all memory instances, inject `self._trace_manager` and the current trace ID onto each instance. On each `run()` call, update `_current_trace_id` on all memory instances to match the new trace.

## Acceptance criteria

- [ ] Runtime's `on_start()` sets `_trace_manager` and `_current_trace_id` on all four memory instances
- [ ] Runtime's `run()` updates `_current_trace_id` on all memory instances at the start of each request
- [ ] `_start_runtime_span`, `_start_profile_span`, `_start_retrieval_span`, `_start_archive_span` return actual `Span` objects (not `None`) during normal operation
- [ ] Test: memory operations appear in trace JSONL output
- [ ] Existing tests pass (`test_memory_spans.py`, `test_trace_jsonl.py`, `test_trace_persistence.py`)

## User stories covered

- US 7: Memory trace spans are correctly recorded to trace logs

## Blocked by

None — can start immediately
