# PRD: Eval System Hardening + Feature Verification

## Problem Statement

项目已完成 19 个 planned task 的全部实现，包括 streaming output、cost tracking、prompt caching、task cancellation、eval runner 五大核心功能。但在审慎分析后发现三个层面的障碍阻止这些功能真正可用：

1. **Critical Bug** — `OpenAIProvider._stream_openai()` 在流式模式下始终丢弃 tool_calls（返回空数组），导致 agent 在 streaming 模式下完全无法调用工具。DeepSeek 继承 OpenAIProvider，同样受影响。
2. **Eval 基础设施缺失** — `evals/` 目录不存在，CLI `agent eval` 未接通 AgentRuntime（抛 NotImplementedError），eval 结果无持久化机制。整个 eval 系统有框架无数据。
3. **零真实验证** — 所有 59 个测试文件均使用 mock，没有任何一次真实 LLM API 调用验证。四个高风险区域（streaming、cancellation、ReAct+工具调用、DeepSeek 兼容性）尚未经真实环境验证。

## Solution

分三步建立可信的测试验证体系：

1. **修复已发现的 bug**（streaming tool_calls 丢失、DeepSeek URL 默认值不一致）
2. **建设 eval 基础设施**（创建 smoke YAML scenario、接通 CLI eval 到 runtime、添加结果持久化）
3. **真实 E2E 验证**（使用 DeepSeek API key 跑通 smoke suite，覆盖四个高风险功能区域）

## User Stories

### Bug Fix

1. 作为开发者，我希望 streaming 模式下 agent 仍然能调用工具，这样我可以在实时输出场景中使用完整 ReAct 循环
2. 作为开发者，我希望 DeepSeek URL 默认值与 config.yaml 一致（`https://api.deepseek.com/v1`），这样在没有 config 文件的场景下也不会发错 API endpoint
3. 作为开发者，我希望 streaming 模式下 tool_calls 的收集逻辑与 non-streaming 模式完全一致，这样两种模式的行为是可互换的

### Eval Scenario 数据

4. 作为 agent 评估者，我希望有一组预定义的 smoke scenario（7 个 YAML 文件），这样我可以快速验证 agent 基本功能路径
5. 作为 agent 评估者，我希望 smoke scenario 覆盖简单问答、文件读取、Shell 执行、搜索、多步推理、中文输入、Self 工具七大路径，这样能快速定位问题所属功能域
6. 作为 agent 评估者，我希望 scenario 按 suite 分组存放（smoke/tools/routing），这样我可以按需跑不同粒度的测试

### CLI Eval 集成

7. 作为开发者，我希望 `agent eval --suite smoke` 能直接连接 AgentRuntime 跑真实 LLM 调用，这样我不需要写代码就能验证 agent 行为
8. 作为开发者，我希望 `agent eval` 在没有配置 runtime 时优雅降级显示 scenario 列表，这样我可以在无 API key 环境下检查 scenario 定义
9. 作为开发者，我希望 eval 结果以 JSON 形式持久化到 `.open_agent/eval_results/` 目录，这样我可以比较不同时间的跑分趋势
10. 作为开发者，我希望 eval 结果记录包含 scenario name、status、checks 详情、output、timestamp、model info，这样我可以追溯历史表现

### E2E 真实验证

11. 作为开发者，我希望有标记 `@pytest.mark.live` 的 E2E 测试，这样 CI 默认跳过但本地可以手动触发真实 API 调用
12. 作为开发者，我希望 E2E 测试验证简单问答的真实 DeepSeek 响应，这样我确认 provider 链路完整可用
13. 作为开发者，我希望 E2E 测试验证工具调用的真实端到端流程（agent 决策 → 工具执行 → 结果返回），这样我确认 ReAct 循环在生产模式下工作
14. 作为开发者，我希望 E2E 测试验证 streaming 模式下的完整 agent 执行（含工具调用），这样我确认修复后的 streaming 不再丢失 tool_calls
15. 作为开发者，我希望 E2E 测试验证 CancellationToken 能真正中断正在进行的 LLM 调用，这样我确认取消机制在生产环境下有效
16. 作为开发者，我希望 E2E 测试能跑完整个 evals/smoke/ suite，这样我一次性获得所有核心路径的验证报告

### 边界条件测试

17. 作为开发者，我希望有 streaming 空 chunk、纯 tool_calls 无 text、chunk 乱序等边界测试，这样 streaming 实现足够健壮
18. 作为开发者，我希望有多层嵌套取消、cancel 后 restart 等边界测试，这样 cancellation 机制在各种场景下都可靠
19. 作为开发者，我希望有 ReAct max_iterations 达上限、工具报错恢复等边界测试，这样 agent 在异常路径下也能优雅处理
20. 作为开发者，我希望有 DeepSeek API 错误响应、rate limit 重试等边界测试，这样 provider 对 DeepSeek 特有的错误模式有正确处理

## Implementation Decisions

### 1. Streaming Tool_Calls 收集方案

在 `_stream_openai()` 中，流式迭代时同步收集 `chunk.choices[0].delta.tool_calls`。OpenAI（及兼容 API）的 streaming tool_calls 格式为增量式：每个 chunk 包含 `index`、`function.name`（仅首个 chunk）、`function.arguments`（逐步拼接）。流结束后按 index 聚合为完整 tool_call 对象，转换为 `ToolCallResponse.tool_calls` 列表。

这与 non-streaming 路径使用相同的输出格式（`ToolCallResponse`），保证下游 ReAct 循环在两种模式下行为一致。

### 2. DeepSeek URL 统一

将 `DeepSeekProvider.__init__` 的 fallback URL 从 `https://api.deepseek.com` 改为 `https://api.deepseek.com/v1`。OpenAI SDK 的 `AsyncOpenAI` 在已包含版本路径时不会重复拼接，因此 `/v1` 后缀是必要的。

### 3. Eval Scenario 目录结构

```
evals/
├── smoke/    # 基础冒烟测试 (7 个)
├── tools/    # 工具专项测试 (5 个)
└── routing/  # 路由测试 (3 个)
```

每个 YAML 文件格式遵循 EvalRunner 已支持的 schema：
```yaml
name: string          # scenario 名称
input: string         # 用户输入
expected_tools: []    # 期望调用的工具名列表
expected_outcome: ""  # 期望输出中包含的子串
```

### 4. CLI Eval 接通 Runtime

在 `eval_cmd` 中，当有 config 且 config 包含有效 provider 时，创建 `AgentRuntime` 实例传给 `EvalRunner`。添加 `--no-runtime` flag 允许只看 scenario 列表不跑实际调用。保持现有的 NotImplementedError 降级路径作为无配置时的后备。

### 5. Eval 结果持久化

EvalRunner 在 `run_suite()` 完成后将结果保存到 `.open_agent/eval_results/<suite>_<timestamp>.json`。每条记录结构：
```json
{
  "suite": "smoke",
  "timestamp": "2026-06-03T14:30:00",
  "model": {"provider": "deepseek", "name": "deepseek-chat"},
  "results": [{"name": "...", "status": "pass/fail", "checks": [...], "output": "..."}],
  "summary": {"total": 7, "passed": 6, "failed": 1}
}
```

### 6. E2E Live 测试标记

使用 `@pytest.mark.live` pytest marker，需要 `DEEPSEEK_API_KEY` 环境变量。在 `pyproject.toml` 的 pytest 配置中注册该 marker，CI 配置中默认排除 `-m "not live"`。

### 7. 测试优先级

先修复 streaming bug → 建立 evals/smoke/ → 接通 CLI eval → 真实 DeepSeek 跑分 → 补充边界测试。

## Testing Decisions

### 测试哲学

- **外部行为优先**：测试 agent 的输入输出行为，不测试内部实现细节（如具体的 provider 方法调用）
- **最高 seams 优先**：E2E 测试通过 `AgentRuntime.run()` 触发，不直接调用 provider 或 ReAct loop
- **Mock 用于隔离，Live 用于验证**：单元测试用 mock 隔离外部依赖，live 测试验证真实端到端

### 模块测试计划

| 模块 | 测试类型 | 测试文件 | 说明 |
|------|----------|----------|------|
| `_stream_openai()` tool_calls | 单元测试 | `test_streaming.py` | Mock streaming chunks，验证 tool_calls 正确收集 |
| `DeepSeekProvider` URL | 单元测试 | `test_provider_hardening.py` | 验证无 config 时 base_url fallback 为 `/v1` 结尾 |
| EvalRunner + Runtime | 集成测试 | `test_eval_runner.py` | Mock provider，验证 runtime 集成和结果格式 |
| EvalRunner 持久化 | 单元测试 | `test_eval_runner.py` | 验证 JSON 结果文件写入和结构 |
| Streaming + DeepSeek | E2E live | `test_e2e_live.py` | 真实 API streaming + tool_calls |
| Cancellation | E2E live | `test_e2e_live.py` | 真实取消中断 |
| ReAct + 工具调用 | E2E live | `test_e2e_live.py` | 真实 agent 工具选择和执行 |
| Eval smoke suite | E2E live | `test_e2e_live.py` | 跑完整 smoke suite |

### Prior Art

- 现有 `test_streaming.py` 已建立 streaming 测试模式（Mock StreamResponse + on_chunk callback）
- 现有 `test_eval_runner.py` 已建立 eval runner 测试模式（tmp_path + YAML + mock response）
- 现有 `test_e2e.py` 提供了端到端测试骨架

## Out of Scope

- **eval 框架扩展**：不新增 `cost_budget`、`max_turns`、`latency` 等检查维度，当前 `expected_tools` + `expected_outcome` 足够起步
- **evals/tools/ 和 evals/routing/ 创建**：先只建 smoke suite，细粒度 suite 后续补充
- **CI 集成**：live 测试不进 CI pipeline，仅本地手动触发
- **LLM Judge 集成**：不接入 LLM-as-Judge 评分，先用规则检查
- **EvalDataset 版本对比**：不使用 dataset.py 的版本化功能，先用文件持久化
- **Anthropic/OpenAI provider 验证**：仅验证 DeepSeek，其他 provider 后续覆盖

## Further Notes

### 已发现的潜在风险

| 风险 | 位置 | 影响 | 本 PRD 处理 |
|------|------|------|-------------|
| Streaming 丢弃 tool_calls | `model.py:_stream_openai()` | Agent 在 streaming 模式下无法调用任何工具 | **修复** |
| DeepSeek URL 不一致 | `model.py:DeepSeekProvider.__init__` | 无 config 时请求错误 endpoint | **修复** |
| `caching: bool` 传给非 Anthropic provider | `config.py:ModelConfig` | 无害但误导 | 不处理 |
| Tool call arguments 解析失败静默返回 `{}` | `model.py:complete_with_tools()` | 工具收到空参数 | 记录，后续处理 |
