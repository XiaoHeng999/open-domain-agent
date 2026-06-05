# Issue 07: E2E — Streaming 模式 + 工具调用真实验证

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在 `tests/test_e2e_live.py` 中添加 E2E 测试，验证 Issue 01 的 streaming tool_calls bug 修复在真实 DeepSeek API 下有效。

测试场景：启用 streaming 模式向 agent 发送需要工具调用的指令（与 Issue 06 类似但开启 `stream=True`），验证：
- streaming 回调收到文本 chunk
- streaming 模式下 tool_calls 不被丢弃（agent 能选择并执行工具）
- 最终输出正确

这是 Issue 01 bug 修复的最终验证——只有通过真实 API 的 streaming + tool_calls 测试才能确认修复有效。

## Acceptance criteria

- [ ] E2E 测试在 streaming 模式下验证 tool_calls 正确收集
- [ ] streaming callback 收到文本 chunk
- [ ] agent 在 streaming 模式下能选择并执行工具
- [ ] 最终输出包含工具返回的信息
- [ ] `pytest tests/test_e2e_live.py -m live -v` 通过（需要 API key）

## Blocked by

- Issue 05: E2E live 测试骨架
- Issue 01: streaming tool_calls bug 修复（验证对象）

## User stories

- #14: 验证 streaming 模式下 agent 能调用工具（确认 bug 已修复）

## Notes

**Type: HITL** — 需要 `DEEPSEEK_API_KEY`。
