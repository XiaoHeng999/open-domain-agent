# PRD: Fast Path 优化 — 简单请求跳过 ReAct 循环

## Problem Statement

当用户发送简单请求（如"你好"、"谢谢"）时，系统虽然通过路由正确识别了 `complexity=simple, intent=greeting, confidence=0.95`，但仍然走完整个 ReAct 循环：构建完整消息（含所有工具定义）→ 调用 LLM API（带 tool definitions）→ LLM 返回纯文本 → 循环退出。

这导致：
1. **延迟浪费** — "你好"耗时 ~3168ms，其中大部分花在不必要的 LLM 调用上
2. **Token 浪费** — LLM 接收了全部工具 schema，但没有调用任何工具
3. **架构信号断裂** — 路由层已经判断出"无需工具"，但这个信号没有被消费

根本原因：`skip_planning` 只跳过了 `PlanGenerator`（runtime.py line 437），ReAct 循环本身没有 fast path。系统中唯一的短路路径是"缺失槽位澄清"（runtime.py line 388），但它不覆盖"可以直接回答的简单请求"。

## Solution

在 `AgentRuntime.run()` 中，planning gate 之前新增一个 fast path 分支。当路由结果满足 `skip_planning=True AND intent.slots 为空 AND intent.missing_slots 为空` 时，跳过 ReAct 循环，直接调用 `provider.complete()` 返回轻量回答。

核心原则：
- **不改路由层** — 复用已有的 `skip_planning`、`slots`、`missing_slots` 信号
- **不改 ReAct 循环** — fast path 在 runtime 层短路，不进入 ReAct
- **不改返回结构** — 返回标准 `AgentResponse`，调用方无需区分
- **保持轻量** — 不走监控/记忆/评估流程，只创建轻量 trace span

## User Stories

1. 作为用户，我希望发送"你好"时能在 <1s 内得到回复，而不是等待 3s 走完 ReAct 循环
2. 作为用户，我希望简单问答（如"Python 是什么？"）能快速回答，不需要系统加载工具定义
3. 作为用户，我希望 chitchat 类请求（"谢谢"、"再见"）不走完整 agent 流程
4. 作为开发者，我希望简单请求不走 ReAct 循环以节省 LLM token 开销
5. 作为开发者，我希望简单请求仍能在 trace 中留有记录，方便排查"为什么这个请求没走 ReAct"
6. 作为开发者，我希望复杂请求完全不受 fast path 影响，仍走完整 ReAct 循环
7. 作为开发者，我希望 fast path 失败时能被 runtime 已有的异常处理机制兜底
8. 作为开发者，我希望子 agent 不受 fast path 影响（子 agent 直接调 ReActLoop.run()，不走 AgentRuntime.run()）
9. 作为开发者，我希望 fast path 条件基于已有的路由信号（slots/missing_slots），不需要维护意图白名单
10. 作为开发者，我希望返回的 AgentResponse 结构统一，CLI 层无需感知 fast path 的存在
11. 作为开发者，我希望 fast path 使用通用 system prompt + 不带工具定义的 LLM 调用，最大化性能收益
12. 作为运维人员，我希望简单请求不写入 episodic memory 和 eval 评分，避免无意义的监控数据

## Implementation Decisions

1. **Fast path 位置**：在 `AgentRuntime.run()` 的 Stage 4（planning gate, line 437）之前插入。与现有 missing_slots clarification fast path（line 388）形成同一层的两个短路分支。

2. **触发条件**：`routing_decision.skip_planning AND not routing_decision.intent.slots AND not routing_decision.intent.missing_slots`。`skip_planning` 已编码了 `complexity == "simple" AND confidence >= 0.9` 的判断，加上 slots 为空确保不需要工具。

3. **LLM 调用方式**：`provider.complete()` 传入 `[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": user_input}]`，`max_tokens=256`。不传工具定义，不注入 profile/todo/skills 上下文。

4. **Trace 处理**：创建一个轻量 `fast_path` span（kind=AGENT_LOOP），记录 intent、domain、answer_len，然后 finish。不进入 Stage 5/6 的监控和记忆流程。

5. **返回结构**：构造标准 `AgentResponse(output=answer, trace_id=trace.trace_id, routing=routing_decision, duration_ms=duration_ms, metadata={"fast_path": True})`，与 missing_slots clarification 的返回模式一致。

6. **异常处理**：不额外 try/except，依赖 `AgentRuntime.run()` 已有的 `except AgentError` 处理链（line 463-481）。

7. **不改 RoutingDecision**：`skip_planning` 语义不变（跳过规划），fast path 条件在 runtime 层用多个已有信号组合判断。

8. **不改 ReAct 循环**：`react.py` 无需修改。子 agent 直接调 `ReActLoop.run()`（subagent/manager.py line 204），天然绕过 fast path。

## Testing Decisions

1. **测试切入点**：在 `tests/test_agent.py` 中新增 `TestFastPath` 测试类，测试 `AgentRuntime` 层行为（最高 seam）。

2. **测试策略**：只测外部行为（是否短路、返回是否正确），不测内部实现细节。

3. **关键测试用例**：
   - 简单问候（"你好"）命中 fast path，`total_steps` 为 0 或 metadata 标记 fast_path
   - 带工具需求的简单请求（有 slots）不命中 fast path，仍走 ReAct
   - 复杂请求不命中 fast path
   - Fast path LLM 调用失败时异常被正确抛出

4. **现有测试先例**：`test_e2e.py::TestMinimalRun::test_hello_task` 已有类似场景的测试模式（route → loop.run），可参考其 mock 方式。

5. **回归测试**：`pytest tests/ -x -q` 全量通过，确保 fast path 不影响正常 ReAct 路径。

## Out of Scope

- 不修改 `RoutingDecision` 数据结构或 `skip_planning` 的计算逻辑
- 不修改 `ReActLoop` 的任何代码
- 不添加 fast path 的开关配置项（默认启用）
- 不对 fast path 的回答做质量评估或 eval 评分
- 不在 fast path 中注入 profile memory、skills、todo plan 等上下文
- 不添加意图白名单（greeting/chitchat 等）
- 不修改子 agent 的调用路径

## Further Notes

### 现有 fast path 先例

`runtime.py` line 388 已有一个 fast path（missing_slots clarification），它直接返回 `AgentResponse` 而不进入 ReAct 循环。新的 fast path 与它在同一层，形成两个独立的短路分支：

```
Routing → missing_slots clarification fast path (line 388)
        → new: simple+no-slots fast path (line ~437, 新增)
        → Planning gate → ReAct Loop (正常路径)
```

### 为什么不在 ReAct 循环内部做 fast path

ReAct 循环是通用执行引擎，被 `AgentRuntime.run()` 和 `SubagentManager` 两处调用。在 runtime 层做短路可以只影响 `AgentRuntime` 路径，子 agent 不受影响。如果在 ReAct 循环内部做，则需要额外区分调用来源。

### 延迟预期

当前"你好"请求耗时 ~3168ms，主要开销在：
- 构建完整消息 + 工具定义: ~50ms
- LLM API 调用（带工具 schema）: ~3000ms
- ReAct 循环框架开销: ~100ms

Fast path 预期开销：
- 轻量 LLM 调用（无工具 schema）: ~500-1000ms
- 预计总延迟: <1000ms
