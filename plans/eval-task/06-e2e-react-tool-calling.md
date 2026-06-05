# Issue 06: E2E — ReAct 循环 + 工具调用真实验证

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在 `tests/test_e2e_live.py` 中添加 E2E 测试，验证 agent 通过真实 DeepSeek 调用执行完整的 ReAct 循环：agent 接收任务 → 决策调用工具 → 工具执行 → 返回观察结果 → 最终回答。

测试场景：向 agent 发送需要调用 `read_file` 工具的指令（如 "Read /etc/hostname and tell me what it says"），验证：
- agent 选择了正确的工具（read_file）
- 工具被实际执行并返回内容
- 最终输出包含文件内容

## Acceptance criteria

- [ ] E2E 测试验证 agent 真实调用 DeepSeek 并选择正确工具
- [ ] 测试验证工具被执行（不只是 agent 声称要调用）
- [ ] 测试验证最终输出包含工具返回的信息
- [ ] `pytest tests/test_e2e_live.py -m live -v` 通过（需要 API key）

## Blocked by

- Issue 05: E2E live 测试骨架（需要 test_e2e_live.py 和 fixture）

## User stories

- #13: 验证 ReAct 循环在真实 DeepSeek 下工作（agent 决策 → 工具执行 → 结果返回）

## Notes

**Type: HITL** — 需要 `DEEPSEEK_API_KEY`。
