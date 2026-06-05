# Issue 09: CI + 趋势分析 + 离线回放

## What to build

为 eval 系统提供 CI 集成、历史趋势对比和离线 trajectory 回放能力。

端到端行为：

**CI 集成**：`make eval` 一键运行 smoke 评估套件。`make eval-trend` 运行评估后展示与上次结果的对比。

**趋势分析**：新增 `open_agent.eval.trend` 模块，可加载多次 eval 历史结果，计算 pass_rate、tool_accuracy 的 delta 变化，识别回归场景（上次 pass 这次 fail 的场景）。通过 `python -m open_agent.eval.trend --latest 2 --suite smoke` 使用。

**离线 trajectory 回放**：新增 `agent eval-replay --trajectory <path> --scenario <path>` 命令。从 JSON 文件反序列化 trace，配合 YAML 场景定义，调用 TraceReplayEngine 重新评估。不需要 LLM 调用，纯离线操作。可用于：
- 用新的断言规则重新评估旧 trajectory
- A/B 测试不同评分阈值
- 回归测试：确保新的断言逻辑不误判历史数据

## Acceptance criteria

- [ ] Makefile 新增 `eval` 目标，运行 `agent eval --suite smoke`
- [ ] Makefile 新增 `eval-trend` 目标，运行趋势对比
- [ ] `open_agent.eval.trend` 模块可加载指定 suite 的最近 N 次 eval 结果
- [ ] 趋势对比输出 delta 表：pass_rate 变化、tool_accuracy 变化、回归场景列表
- [ ] `agent eval-replay` 命令接受 `--trajectory` 和 `--scenario` 参数
- [ ] 离线回放从 JSON 反序列化 trace，调用 TraceReplayEngine，输出 ReplayResult
- [ ] 离线回放过程无 LLM API 调用
- [ ] 测试覆盖：趋势对比逻辑、trajectory 反序列化

## Blocked by

- Issue 05: Eval 接入 TraceReplayEngine（需要 ReplayResult 格式）
- Issue 07: Eval 聚合指标 + Trajectory 持久化（需要 trajectory 文件才能回放）

## User stories

- #17 `make eval` 一键运行 smoke 评估
- #18 趋势对比工具比较多次 eval 的 pass_rate 和 tool_accuracy 变化
- #19 离线 trajectory 回放，不需要 LLM 调用
