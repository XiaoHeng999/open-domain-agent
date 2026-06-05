# Issue 05: Eval 接入 TraceReplayEngine（路径 B）

## What to build

将 CLI eval 从弱断言（子串匹配）切换到严格断言（TraceReplayEngine），同时保持 YAML 格式向后兼容。

端到端行为：`agent eval --suite smoke` 执行时，每个 YAML 场景被转换为 `Scenario` 数据class，通过 runtime 执行后获取 trace，然后用 TraceReplayEngine 进行有序工具调用对比 + 结构化断言检查。评估结果包含 tool_call_accuracy 和 assertion_pass_rate，而不再是简单的 "工具名是否在 action 字符串中出现"。

YAML 格式向后兼容：
- 旧格式（`expected_tools` + `expected_outcome`）自动转换为等价的 Scenario
- 新格式支持 `assertions` 字段，指定 `tool_called_with`、`output_contains`、`output_matches`、`state_equals` 四种断言
- 现有 7 个 smoke YAML 不需要任何修改

EvalRunner 重写要点：
- `load_suite` 返回 `list[Scenario]`（而非 `list[dict]`）
- `_run_scenario` 通过 runtime.run → trace_manager.get_trace → TraceReplayEngine.replay 获取 ReplayResult
- 删除旧的 `_check_expectations` 子串匹配逻辑

## Acceptance criteria

- [ ] EvalRunner 新增 `_yaml_to_scenario()` 方法，将 YAML dict 转换为 Scenario 数据class
- [ ] 旧格式 YAML（只有 expected_tools + expected_outcome）被正确转换为等价的 Scenario
- [ ] 新格式 YAML（带 assertions 字段）被正确解析为 StepAssertion 列表
- [ ] `_run_scenario` 使用 TraceReplayEngine 进行评估（不再使用子串匹配）
- [ ] CLI eval 输出包含 tool_call_accuracy 和 assertion_pass_rate 字段
- [ ] CLI eval 表格增加 "Tool Accuracy" 列
- [ ] 现有 7 个 smoke YAML 不修改即可运行
- [ ] 现有 eval 测试更新后通过

## Blocked by

- Issue 01: Trace 持久化（EvalRunner 需要从 TraceManager 获取 trace）

## User stories

- #9 eval 使用 TraceReplayEngine 进行评估
- #10 YAML 场景支持结构化断言
- #11 YAML 格式向后兼容
