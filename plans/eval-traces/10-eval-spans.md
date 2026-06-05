# Issue 10: Eval spans 可观测（EVAL spans）

## What to build

让 eval 执行过程被 trace 覆盖，记录每个 eval 场景的 replay 过程和断言结果。

端到端行为：当 eval 运行时（通过 `run_eval_scenario` 或 CLI eval），replay 过程在 trace 中创建 `EVAL` 类型的 span，记录场景名称、工具调用准确率、断言通过率、最终 pass/fail 状态。这样通过 trace 可以看到 eval 本身的执行情况，便于调试 eval 规则是否合理。

## Acceptance criteria

- [ ] `runtime.run_eval_scenario` 中创建 EVAL span，属性包含 scenario、passed
- [ ] EvalRunner._run_scenario 中（通过 trace_manager）创建 EVAL span，记录评估结果
- [ ] Eval 完成后 span 属性包含 tool_accuracy、assertion_rate，并调用 finish()
- [ ] 运行 eval 后的 trace 中包含 `"kind": "eval"` 类型的 span
- [ ] 至此，所有 9 种 SpanKind 都有实际使用

## Blocked by

- Issue 05: Eval 接入 TraceReplayEngine（需要新的 eval pipeline 中的 trace 创建点）

## User stories

- #8 eval 执行过程被 trace 覆盖
