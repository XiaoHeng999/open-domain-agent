# Issue 08: E2E — Task Cancellation 真实验证

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在 `tests/test_e2e_live.py` 中添加 E2E 测试，验证 CancellationToken 能真正中断正在进行的 DeepSeek API 调用。

测试场景：
1. 启动一个 agent run 任务
2. 在任务执行过程中（LLM 调用进行中）触发 cancellation
3. 验证 agent 优雅退出（不 crash），返回部分结果或取消标记
4. 验证取消后资源正确清理

这验证了 cancellation 机制不只是单元测试层面的 mock 行为，而是在真实网络 I/O 场景下有效。

## Acceptance criteria

- [ ] E2E 测试验证 CancellationToken 能中断真实 DeepSeek API 调用
- [ ] 取消后 agent 不 crash，优雅退出
- [ ] 取消后的 ReAct loop 状态正确（step count 正确、trace 完整）
- [ ] `pytest tests/test_e2e_live.py -m live -v` 通过（需要 API key）

## Blocked by

- Issue 05: E2E live 测试骨架

## User stories

- #15: 验证 CancellationToken 能中断真实 LLM 调用

## Notes

**Type: HITL** — 需要 `DEEPSEEK_API_KEY`。
