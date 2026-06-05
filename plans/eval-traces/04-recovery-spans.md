# Issue 04: Recovery 可观测（RECOVERY spans）

## What to build

让 recovery 策略链的执行过程被 trace 覆盖，使其可观测。

端到端行为：当 agent 在 ReAct 循环中遇到工具执行错误时，触发 recovery chain。整个 recovery 过程（错误分类 → 策略查找 → 链式执行）在 trace 中创建 `RECOVERY` 类型的 span，记录错误类型、尝试的策略、最终状态。通过 `agent trace <id>` 查看时，能看到哪个工具失败、触发了什么恢复策略、是否成功恢复。

需要修改两处：
1. ReActLoop._try_recover 接收 trace 参数并传递给 recovery engine
2. RecoveryChain.execute 从 context 中提取 trace 并创建 RECOVERY span

## Acceptance criteria

- [ ] ReActLoop._try_recover 签名增加 `trace` 参数
- [ ] ReActLoop._execute_action 调用 _try_recover 时传入 trace
- [ ] RecoveryChain.execute 创建 RECOVERY span，属性包含 error_type、strategy_count
- [ ] Recovery 完成后 span 记录 final_status 并调用 finish()
- [ ] 触发工具错误后，持久化的 trace JSON 中包含 `"kind": "recovery"` 类型的 span
- [ ] 现有 recovery 测试不受影响

## Blocked by

- Issue 01: Trace 持久化（需要 trace 能写入磁盘才能验证）

## User stories

- #7 recovery 策略链的执行被 trace 覆盖
