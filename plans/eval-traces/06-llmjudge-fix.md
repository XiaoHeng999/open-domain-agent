# Issue 06: LLMJudge 评分修复

## What to build

重写 LLMJudge 的 `_rule_based_judge` 兜底评分逻辑，从"任何非空输出 4 分"改为多信号渐进评分，让评分有实际区分度。

端到端行为：当 eval 运行且没有配置 LLM provider 时，使用规则兜底评分。评分不再是"空=1、其他=4"，而是根据输出长度、期望内容匹配度、输出结构质量三个信号渐进打分：

| 分数 | 条件 | 含义 |
|---|---|---|
| 1.0 | 输出为空或纯空白 | 完全失败 |
| 2.0 | 输出 < 20 字符 | 严重不足 |
| 2.5 | 有输出但期望内容完全未出现 | 偏题 |
| 3.0 | 期望内容关键词部分出现 | 部分正确 |
| 4.0 | 期望内容完整出现 | 正确 |
| 4.5-5.0 | 完整匹配 + 输出结构良好 | 优秀 |

每个等级附带 reasoning 文本。之后将 LLMJudge 接入 eval pipeline，在 TraceReplayEngine 评估完成后额外调用 judge 获取质量评分。

## Acceptance criteria

- [ ] `_rule_based_judge` 重写为多信号渐进评分（6 个等级）
- [ ] 空输出评分 1.0，短输出评分 2.0，不再出现"非空即 4 分"
- [ ] 每个 JudgeScore 包含描述性 reasoning 文本
- [ ] LLMJudge 在 EvalRunner._run_scenario 中被调用，评分写入结果
- [ ] LLM provider 可用时的 LLM 评分路径不受影响
- [ ] 测试覆盖：各等级的输入输出评分正确

## Blocked by

- Issue 05: Eval 接入 TraceReplayEngine（需要在新的 eval pipeline 中接入 judge）

## User stories

- #12 LLMJudge 兜底评分有实际区分度
