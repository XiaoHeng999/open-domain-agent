# Issue 08: Monitoring 边界清理

## What to build

明确 Monitoring 和 Eval 的职责边界，让 Monitoring 只负责实时异常检测和告警，评分权威统一到 Eval。

端到端行为：

**QualityScorer 降级**：`monitoring/collector.py` 中的 `QualityScorer` 类保留（不删除，避免 breaking change），但标记为 deprecated。`AgentRuntime.quality_score` 字段继续填充以保持向后兼容，但注释标明权威评分在 `eval.metrics.compute_metrics()`。

**FeedbackLoop 接入**：`FeedbackLoop.suggest_eval_case()` 当前是孤儿方法（从未被调用）。在 runtime.run() 中，anomaly detection 之后调用此方法，当 trace 质量分 ≥ 80 时自动 log 推荐。此方法未来可扩展为自动保存 eval 候选用例。

**职责确认**：
- Monitoring 模块只保留：AnomalyDetector（异常检测）、TraceCollector（实时查询）、FeedbackLoop（反馈循环）
- QualityScorer 保留但 deprecated
- 所有评分逻辑归 Eval 模块

## Acceptance criteria

- [ ] QualityScorer 类添加 deprecated 文档说明
- [ ] AgentRuntime.run 中 quality_scorer.score() 调用保留，注释标明 deprecated
- [ ] FeedbackLoop.suggest_eval_case() 在 runtime.run() 中被调用
- [ ] suggest_eval_case 返回非 None 时 logger.info 记录推荐
- [ ] 现有 monitoring 测试全部通过（不删除 QualityScorer）
- [ ] Monitoring 模块不新增任何评分逻辑

## Blocked by

- Issue 05: Eval 接入 TraceReplayEngine（需要 Eval 成为评分权威后才能降级 Monitoring 的评分）

## User stories

- #15 Monitoring 只负责实时异常检测，不输出质量分数
- #16 FeedbackLoop 被正确接入，高质量 trace 被推荐为 eval 候选
