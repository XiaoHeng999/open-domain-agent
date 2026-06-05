# agent/ — 执行引擎

- `react.py` — ReAct 循环：Thought → Action → Observation，含 6 种确定性停止条件
- `planner.py` — PlanGenerator：复杂任务的可选规划步骤（LLM 或规则）
