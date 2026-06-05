# Issue 07: Eval 聚合指标 + Trajectory 持久化

## What to build

将 `compute_metrics` 聚合指标接入 eval pipeline，并持久化完整 trajectory 用于离线回放。

端到端行为：

**聚合指标**：`agent eval --suite smoke` 运行完成后，eval 报告 JSON 中包含 `metrics` 字段，记录 tool_call_success_rate、task_completion_rate、avg_turns 等跨场景聚合指标。这些指标由 `eval/metrics.py` 的 `compute_metrics()` 从所有 ReplayResult 中计算得出。

**Trajectory 持久化**：每次 eval 运行时，每个场景的完整 trace JSON 被保存到 `.open_agent/eval_results/trajectories/` 子目录，文件名格式为 `{scenario_name}_{trace_id}.json`。这些 trajectory 可用于：
- 离线回放（不调用 LLM 重新评估）
- 深度分析 agent 决策过程
- 训练数据生成

目录结构：
```
.open_agent/eval_results/
├── smoke_20260604T103000Z.json          # eval 报告（含 metrics）
└── trajectories/
    ├── tool_read_abc123.json
    └── multi_step_def456.json
```

## Acceptance criteria

- [ ] EvalRunner.run_suite 完成后调用 compute_metrics，聚合指标写入报告 JSON 的 "metrics" 字段
- [ ] 报告 JSON 包含 tool_call_success_rate、task_completion_rate、avg_turns、per_scenario
- [ ] 每个场景的完整 trace JSON 被保存到 trajectories/ 子目录
- [ ] trajectory 文件可通过 trace_id 与报告中的结果条目关联
- [ ] Trajectory 持久化失败不影响报告生成（try/except 包裹）
- [ ] 测试覆盖：验证 trajectories/ 目录和文件存在

## Blocked by

- Issue 05: Eval 接入 TraceReplayEngine（需要 ReplayResult 才能计算指标）

## User stories

- #13 eval 结果中包含聚合指标
- #14 eval 保存完整的 trajectory 用于离线回放
