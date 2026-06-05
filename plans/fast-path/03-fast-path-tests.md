# 03: Fast Path 测试

## Type
AFK

## Parent

PRD-05: Fast Path 优化 — 简单请求跳过 ReAct 循环

## What to build

在 `tests/test_agent.py` 中新增 `TestFastPath` 测试类，覆盖 fast path 的所有行为：命中条件、未命中条件、返回结构、trace span 创建、异常处理。使用 mock provider 避免 LLM API 调用。参考现有 `test_e2e.py::TestMinimalRun::test_hello_task` 的 mock 模式。

## Acceptance criteria

- [ ] 测试简单问候（"你好"）命中 fast path，验证 metadata 含 `fast_path: True`
- [ ] 测试带 slots 的请求不命中 fast path，仍走 ReAct
- [ ] 测试复杂请求（skip_planning=False）不命中 fast path
- [ ] 测试返回的 AgentResponse 结构完整（output、trace_id、routing、duration_ms）
- [ ] 测试 fast_path span 在 trace 中存在且属性正确
- [ ] 测试 provider.complete() 失败时异常正确抛出
- [ ] `pytest tests/ -x -q` 全量通过

## User stories covered

- 所有 US 的验证覆盖

## Blocked by

- 01: Fast Path 核心分支
- 02: Fast Path Trace Span
