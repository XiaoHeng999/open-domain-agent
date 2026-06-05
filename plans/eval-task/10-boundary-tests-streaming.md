# Issue 10: 边界条件测试 — Streaming

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在现有 `tests/test_streaming.py` 中补充 streaming 实现的边界条件测试，确保 `_stream_openai()` 在各种异常场景下都能正确处理：

1. **空 chunk 序列**：流式响应只包含 message_start 和 message_delta，无 content_block_delta。应返回空文本和空 tool_calls。
2. **纯 tool_calls 无 text**：所有 chunk 只有 tool_calls delta，无 text content。应正确收集 tool_calls，text 为空。
3. **chunk 乱序/异常 index**：tool_calls delta 的 index 不连续或重复。应按 index 正确聚合。
4. **arguments 跨 chunk 拼接**：一个 tool_call 的 arguments 分散在多个 chunk 中。应完整拼接。
5. **streaming 中途错误**：流式迭代中抛出异常。应优雅处理不 crash。

所有测试使用 mock，不需要真实 API 调用。

## Acceptance criteria

- [ ] 新增至少 5 个 streaming 边界条件测试
- [ ] 覆盖空 chunk、纯 tool_calls、index 异常、arguments 拼接、中途错误
- [ ] `pytest tests/test_streaming.py -v` 全部通过
- [ ] `pytest tests/ -x -q` 全部通过

## Blocked by

- Issue 01: streaming tool_calls bug 修复（边界测试基于修复后的实现）

## User stories

- #17: streaming 空 chunk、纯 tool_calls 无 text、chunk 乱序等边界测试
