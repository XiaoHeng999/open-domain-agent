# 01: Fast Path 核心分支

## Type
AFK

## Parent

PRD-05: Fast Path 优化 — 简单请求跳过 ReAct 循环

## What to build

在 `AgentRuntime.run()` 的 planning gate 之前插入 fast path 分支。当路由决策满足 `skip_planning=True AND intent.slots 为空 AND intent.missing_slots 为空` 时，跳过 ReAct 循环、规划、监控和记忆流程，直接调用 `provider.complete()` 返回轻量回答。

LLM 调用使用通用 system prompt（"You are a helpful assistant."），不传工具定义，不注入 profile/todo/skills 上下文。返回标准 `AgentResponse`（`output=answer, trace_id, routing, duration_ms, metadata={"fast_path": True}`），与现有 missing_slots clarification 的返回模式一致。

## Acceptance criteria

- [ ] `AgentRuntime.run()` 在 planning gate 前检测 `skip_planning AND not slots AND not missing_slots`
- [ ] 命中 fast path 时调用 `provider.complete()` 而非 `provider.complete_with_tools()`
- [ ] 返回标准 `AgentResponse`，`metadata` 含 `{"fast_path": True}`
- [ ] "你好"等简单问候命中 fast path，不进入 ReAct 循环
- [ ] 有 slots 的请求不命中 fast path，仍走正常 ReAct
- [ ] 复杂请求不命中 fast path
- [ ] `pytest tests/ -x -q` 全量通过

## User stories covered

- US 1: 简单请求 <1s 响应
- US 2: 简单问答快速回答
- US 3: chitchat 不走完整 agent 流程
- US 4: 节省 LLM token
- US 6: 复杂请求不受影响
- US 7: 异常被 runtime 已有机制兜底
- US 8: 子 agent 不受影响
- US 9: 基于路由信号，不需意图白名单
- US 10: 返回结构统一
- US 11: 通用 system prompt + 不带工具定义
- US 12: 不写监控/记忆数据

## Blocked by

None — can start immediately
