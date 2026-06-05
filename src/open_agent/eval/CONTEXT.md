# eval/ — 评估框架

- `scenario.py` — 场景定义（步骤断言、预期工具调用）
- `assertions.py` — 断言检查器（output_matches, tool_called_with 等）
- `replay.py` — TraceReplayEngine：回放执行追踪
- `metrics.py` — EvalMetrics：意图准确率、工具成功率、完成率
- `judge.py` — LLMJudge：LLM-as-Judge 评分
- `dataset.py` — 评估数据集工具
