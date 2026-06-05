# Issue 03: 接通 CLI eval 到 AgentRuntime + --no-runtime 降级

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

当前 CLI `agent eval` 命令创建 `EvalRunner` 时未传入 runtime，导致 `_execute_scenario()` 抛 `NotImplementedError`。需要：

1. 在 `eval_cmd` 中，当有有效 config 且 provider 可用时，创建 `AgentRuntime` 实例并传给 `EvalRunner`
2. 添加 `--no-runtime` flag（默认 false），允许只加载 scenario 不跑实际调用
3. 保持现有的 NotImplementedError 降级路径作为无 API key 时的后备行为

完成后补充集成测试：mock provider，验证 EvalRunner 能通过 runtime 执行 scenario 并返回正确结果。

## Acceptance criteria

- [ ] `agent eval --suite smoke --dir evals`（有 API key 时）创建 AgentRuntime 并执行 scenario
- [ ] `agent eval --suite smoke --dir evals --no-runtime` 只显示 scenario 列表不跑调用
- [ ] 无 API key 时优雅降级显示 scenario 列表（不 crash）
- [ ] Rich table 正确显示每个 scenario 的 pass/fail 状态和 checks 详情
- [ ] 新增 mock provider 集成测试验证 runtime 集成
- [ ] `pytest tests/ -x -q` 全部通过

## Blocked by

- Issue 01: 修复 streaming tool_calls bug（streaming 修复后才能跑真实场景）

## User stories

- #7: `agent eval --suite smoke` 能连接 runtime 跑真实 LLM 调用
- #8: 无 runtime 时优雅降级显示 scenario 列表
