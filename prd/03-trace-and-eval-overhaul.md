# PRD: Trace & Eval 系统全面改造

## 问题陈述

open_agent 的 Trace 和 Eval 系统存在 7 个架构层面的缺陷，导致 trace 信息无法持久化、eval 评估不够严格、评分体系混乱、离线分析和 CI 集成缺失：

1. **Trace 持久化缺失** — TraceManager 只存内存 dict，进程退出数据全丢。`agent trace` CLI 命令从磁盘读 JSON 文件，但无代码写入，永远返回 "Trace not found"。
2. **调试信息暴露给普通用户** — 每次 CLI 对话都输出 `📊 Trace: xxx | Steps: x | Duration: xxxms`，这是开发者调试信息，不应默认展示。
3. **Span 覆盖不完整** — SpanKind 定义了 MEMORY_OP、RECOVERY、EVAL 三种类型，但全代码库无任何地方创建这些 span。Memory 操作、恢复策略、eval 执行过程处于不可观测状态。
4. **Eval 使用弱断言** — CLI eval 使用路径 A（简单子串匹配：在 action 字符串里找工具名、在 output 里找子串），而更严格的路径 B（TraceReplayEngine：有序工具调用对比 + 4 种结构化断言）已实现但未接入 CLI。
5. **LLMJudge 评分失效** — 兜底评分规则：空输出 1 分，非空超过 10 字符直接 4 分。这意味着任何答非所问的回复都能拿 80% 分，评估结果无参考价值。
6. **Eval 缺乏消费闭环** — 结果写入 `.open_agent/eval_results/` 但无历史趋势对比、无回归检测、无 CI 集成、无 trajectory 保存用于离线回放。
7. **Monitoring 与 Eval 评分重叠** — `monitoring/collector.py` 的 `QualityScorer` 和 `eval/metrics.py` 的 `compute_metrics` 都在做"评分"，计算逻辑不同但语义重叠，职责边界不清。

## 解决方案

通过 5 个递进阶段，建立 **Trace（采集）→ Monitoring（实时告警）→ Eval（离线评分）** 三层清晰架构。

### 核心架构决策

经过讨论确定的三层边界：

| 层 | 职责 | 做什么 | 不做什么 |
|---|---|---|---|
| **Trace** | 纯记录层 | 采集 span 数据（操作名、属性、耗时、状态） | 不做任何判断或评分 |
| **Monitoring** | 实时观察层 | 在线异常检测（工具循环、重复错误、超时）、实时告警 | 不做评分，不输出质量分数 |
| **Eval** | 离线评估层 | 事后质量评估（评分、断言、趋势、回归检测） | 不做实时告警，是唯一的评分权威入口 |

## 用户故事

### Trace 基础设施

1. 作为开发者，我希望 trace 在进程退出后仍然可查，这样我可以在事后分析某次对话的完整执行链路
2. 作为开发者，我希望 `agent trace <trace_id>` 能正常工作，这样我能查看任意一次对话的路由决策、工具调用、ReAct 迭代详情
3. 作为普通用户，我不希望每次对话都看到 trace ID 和调试信息，除非我主动开启详细模式
4. 作为开发者，我希望通过 `--verbose` 或 `--debug` 标志控制调试信息的显示，这样我可以在需要时查看 trace 信息
5. 作为运维人员，我希望 trace 存储路径可通过环境变量配置（如 `OPEN_AGENT_TRACE_DIR`），这样我可以把 trace 存到持久卷或共享存储

### Span 可观测性

6. 作为开发者，我希望 memory 子系统的读写操作被 trace 覆盖，这样我能看到每次对话触发了哪些 memory 读写、压缩、检索操作
7. 作为开发者，我希望 recovery 策略链的执行被 trace 覆盖，这样我能看到错误触发了哪种恢复策略、执行结果如何
8. 作为开发者，我希望 eval 执行过程被 trace 覆盖，这样我能看到每个 eval 场景的 replay 过程和断言结果

### Eval 系统改造

9. 作为 agent 评估者，我希望 eval 使用严格的 TraceReplayEngine 进行评估（路径 B），这样工具调用是有序对比、断言是结构化检查而非简单子串匹配
10. 作为 agent 评估者，我希望 YAML 场景支持结构化断言（`assertions` 字段），这样我可以检查工具调用参数、输出匹配、状态验证等更精确的条件
11. 作为 agent 评估者，我希望 YAML 格式保持向后兼容，这样现有的 7 个 smoke YAML 不需要修改
12. 作为 agent 评估者，我希望 LLMJudge 的兜底评分有实际区分度，空输出 1 分、短输出 2 分、部分匹配 3 分、完整匹配 4 分，而非"任何非空输出都 4 分"
13. 作为 agent 评估者，我希望 eval 结果中包含聚合指标（工具成功率、任务完成率、平均轮数），这样我可以快速判断整体质量
14. 作为 agent 评估者，我希望 eval 保存完整的 trajectory（trace JSON），这样我可以离线回放和分析每次评估的完整执行过程

### Monitoring 边界

15. 作为开发者，我希望 Monitoring 模块只负责实时异常检测和告警，不输出质量分数，这样"评分"的职责不会在 Monitoring 和 Eval 之间模糊
16. 作为开发者，我希望 Monitoring 的 FeedbackLoop 被正确接入（当前 `suggest_eval_case` 是孤儿方法从未被调用），这样高质量 trace 能被自动推荐为 eval 候选用例

### CI 与趋势分析

17. 作为开发者，我希望有 `make eval` 目标一键运行 smoke 评估，这样可以在 CI 或本地快速验证
18. 作为开发者，我希望有趋势对比工具比较多次 eval 的 pass_rate 和 tool_accuracy 变化，这样我能发现回归
19. 作为开发者，我希望支持离线 trajectory 回放，这样我可以在不调用 LLM 的情况下重新评估已保存的执行轨迹

## 设计决策

### 1. Trace 持久化策略

TraceManager 在 `on_stop` 时批量写入磁盘（每个 trace 一个 JSON 文件到 `trace_dir`）。选择 `on_stop` 而非"每次 run 后立即写入"是因为：
- 减少磁盘 IO 频次
- 确保一个 session 的所有 trace 在退出时完整保存
- 用 try/except 包裹确保持久化失败不阻塞正常关闭

### 2. Memory/Recovery Span 注入方式

采用**实例级属性注入**而非参数透传：
- Runtime 在每次 `run()` 开始时注入 `_current_trace_id` 到各 memory 实例
- Memory 子系统通过 `_trace_manager` + `_current_trace_id` 定位当前 trace，按需创建 span
- 优点：不修改 MemoryManager ABC 接口（避免 breaking change），memory 层可选择性地创建 span

### 3. Eval 路径统一为路径 B

废弃路径 A（子串匹配），统一使用路径 B（TraceReplayEngine）：
- YAML 加载后转换为 `Scenario` 数据class
- 执行后从 TraceManager 获取 trace，调用 TraceReplayEngine.replay
- 旧的 `expected_tools` + `expected_outcome` 字段自动转换为等价的 StepAssertion（向后兼容）

### 4. LLMJudge 评分重设计

从"二值判断"（空 vs 非空）改为**多信号渐进评分**：

| 分数 | 条件 | 含义 |
|---|---|---|
| 1.0 | 输出为空或纯空白 | 完全失败 |
| 2.0 | 输出短于 20 字符，无有意义内容 | 严重不足 |
| 2.5 | 有输出但期望内容完全未出现 | 偏题 |
| 3.0 | 期望内容的关键词部分出现 | 部分正确 |
| 4.0 | 期望内容完整出现 | 正确 |
| 4.5-5.0 | 完整匹配 + 输出结构良好（多句、有组织） | 优秀 |

每个等级附带 reasoning 文本，方便追溯评分依据。

### 5. Monitoring 与 Eval 评分边界

- `QualityScorer` 降级为**兼容层**（保留类和接口但标记 deprecated），`AgentResponse.quality_score` 继续填充以保持向后兼容
- **权威评分**统一到 `eval.metrics.compute_metrics()`，所有新的评分逻辑都在 eval 模块
- `FeedbackLoop.suggest_eval_case` 接入 runtime，当 trace 质量分 ≥ 80 时自动推荐为 eval 候选

### 6. Eval Trajectory 持久化

每次 eval 结果持久化时，同时保存完整 trace JSON 到 `trajectories/` 子目录：
```
.open_agent/eval_results/
├── smoke_20260604T103000Z.json          # eval 报告（含 metrics 聚合）
└── trajectories/
    ├── tool_read_abc123.json            # 完整 trace
    └── multi_step_def456.json           # 完整 trace
```

## 阶段目标

### Phase 1: Trace 基础设施
- TraceManager 增加磁盘持久化能力（persist / load / list）
- Runtime 在 on_stop 时自动持久化所有 trace
- CLI 增加 `--verbose` / `--debug` 全局标志
- Trace 调试信息默认隐藏，仅在 verbose 模式下显示
- `agent trace <id>` 命令可用
- Config 支持环境变量覆盖 trace_dir

### Phase 2: 补全 Span 覆盖
- RuntimeMemory / ProfileMemory / RetrievalMemory / ArchiveMemory 添加 MEMORY_OP span
- RecoveryChain 及各恢复策略添加 RECOVERY span
- Eval replay 过程添加 EVAL span
- 确保所有 9 种 SpanKind 都有实际使用

### Phase 3: Eval 系统改造
- CLI eval 接入 TraceReplayEngine（路径 B），废弃子串匹配
- YAML 格式支持结构化 `assertions` 字段（向后兼容旧格式）
- LLMJudge 兜底评分改为多信号渐进评分
- `compute_metrics` 接入 eval pipeline，聚合指标写入报告
- Trajectory（完整 trace）持久化到 trajectories/ 子目录

### Phase 4: Monitoring 边界清理
- QualityScorer 标记 deprecated，权威评分统一到 eval
- FeedbackLoop.suggest_eval_case 接入 runtime
- Monitoring 模块只保留实时异常检测职责

### Phase 5: CI + 趋势分析
- Makefile 增加 `eval` 和 `eval-trend` 目标
- 趋势对比工具：加载多次 eval 结果，计算 pass_rate / tool_accuracy delta，识别回归场景
- 离线 trajectory 回放：从 JSON 反序列化 trace，调用 TraceReplayEngine 重新评估

## 验收标准

1. `agent run "hello"` 不显示 trace 信息；`agent run "hello" --verbose` 显示 trace 信息
2. `agent run "hello" --verbose` 后，`agent trace <id>` 能正常输出完整 trace JSON
3. Trace JSON 中包含 `memory_op`、`recovery`（当有错误时）、`eval` 类型的 span
4. `agent eval --suite smoke` 使用 TraceReplayEngine 评分，结果包含 tool_call_accuracy 和 assertion_pass_rate
5. LLMJudge 对空输出评 1 分，对答非所问评 2-2.5 分，对正确回答评 4 分
6. `.open_agent/eval_results/` 中同时存在报告 JSON 和 trajectories/ 子目录
7. `make eval` 成功运行并输出 smoke 评估结果
8. 运行两次 eval 后，趋势对比工具能输出 delta 表
9. `pytest tests/ -x` 全部通过
10. Monitoring 的 QualityScorer 标记 deprecated 但不删除，现有测试通过

## Out of Scope

- **跨进程 Trace 关联**：不实现分布式 trace 的 parent-child 跨进程关联
- **Trace 采样策略**：不实现基于采样率的 trace 收集，全部记录
- **实时 Trace 流式推送**：不实现 WebSocket 等实时 trace 推送
- **Anthropic / OpenAI provider 验证**：eval 验证以 DeepSeek 为主
- **evals/tools/ 和 evals/routing/ 创建**：先聚焦 smoke suite
- **CI pipeline 配置**：只提供 Makefile 目标，不配置 GitHub Actions workflow
- **State equals 断言完善**：`assertions.py` 中的 `state_equals` 当前只做顶层 dict 对比，暂不实现嵌套 key 路径导航

## Further Notes

### 已识别的潜在风险

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Phase 3 重写 EvalRunner 可能破坏现有测试 | eval 单元测试全挂 | 保留旧方法作为 legacy fallback，新方法逐步切换 |
| Memory span 创建影响运行时性能 | 每次读写多一次 span 创建开销 | 用 `hasattr` 检查，tracing 关闭时零开销 |
| YAML → Scenario 转换的边界情况 | 旧格式遗漏转换 | 所有 7 个现有 smoke YAML 必须不修改即可运行 |
| Trajectory 文件过大 | 长对话的 trace JSON 可能数 MB | 可接受，离线分析场景下磁盘空间不是瓶颈 |

### 与现有 PRD 的关系

- 本文档是 `02-PRD-eval-system-and-testing.md` 的演进版，覆盖并扩展了其中 eval 相关内容
- `02-PRD` 中的 bug 修复（streaming tool_calls）已完成，不在此重复
- `02-PRD` 中的 E2E live 测试标记体系继续沿用
