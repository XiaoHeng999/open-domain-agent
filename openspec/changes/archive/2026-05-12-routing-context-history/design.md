## Context

当前 routing pipeline 是无状态的：`UnifiedLLMRouter.route()` 只接收 `user_input` 字符串，不接收任何对话历史。这导致 LLM 在 routing 阶段无法做指代消解（"再加100" → 上一轮的 "4"），从而误判 `missing_slots`，触发提前返回跳过 ReAct loop。

ReAct loop 本身已具备多轮上下文能力（`_build_messages()` 读取 `RuntimeMemory`），但 routing 层的 missing_slots 提前返回使其根本没机会被调用。

数据流现状：
```
runtime.run(user_input)
  → routing_pipeline.route(user_input)          # 无状态，只看当前输入
    → UnifiedLLMRouter.route(user_input)         # messages = [system, user_input]
  → if missing_slots: return clarification       # 提前返回，不写 memory
  → react_loop.run(user_input)                   # 这里有历史但到不了
  → runtime_memory.add_message(...)              # 这之后才写 memory
```

## Goals / Non-Goals

**Goals:**
- 让 routing LLM 看到最近 2-3 轮对话历史，使其能正确解析指代和省略
- 将 token 成本增量控制在每轮 +200-500 tokens
- 向后兼容：history 为空时行为与改动前完全一致
- 改动集中在 routing 层，不改变 ReAct loop 或 memory 机制

**Non-Goals:**
- 不重构 routing 为有状态组件——仍然每次调用传入 history，而非 router 内部持有状态
- 不改变 missing_slots 的澄清逻辑——仍然由 runtime 判断并提前返回
- 不改变 RuntimeMemory 的存储时机（post-ReAct 写入）
- 不替代方案 C（干掉 routing）——那是长期方向，本次不改架构

## Decisions

### D1: history 在 routing pipeline 层注入，而非在 UnifiedLLMRouter 内部获取

**选择**：`RoutingPipeline.route()` 接收 `history` 参数，透传给 `UnifiedLLMRouter.route()`。

**理由**：UnifiedLLMRouter 不应依赖 RuntimeMemory——它是一个通用的路由组件，可能在非 runtime 上下文中复用（如 evaluate、测试）。由调用方（runtime → pipeline → router）负责提供上下文，保持组件解耦。

**替代方案**：让 UnifiedLLMRouter 直接引用 RuntimeMemory → 耦合太强，不可取。

### D2: history 截断策略——最近 4 条消息（2 轮）

**选择**：`runtime.py` 在调用 routing_pipeline.route() 时，从 RuntimeMemory 取最近 4 条消息（2 轮 user+assistant），不传全量历史。

**理由**：
- 指代消解通常只需要最近 1-2 轮上下文
- 2 轮 ≈ 200-400 tokens（中文），在成本控制范围内
- 如果需要更多上下文，RuntimeMemory 的 rolling summary 机制已自动压缩早期对话

**替代方案**：传全量历史 → token 成本不可控，随对话增长线性增加。

### D3: keyword fallback path 不传 history

**选择**：keyword 三阶段管线（`_route_keyword`）不接收 history，保持不变。

**理由**：keyword 管线是 fallback 路径，基于子串匹配，history 对它没有意义。且 fallback 本身已意味着 LLM 调用失败，不应增加复杂度。

### D4: system prompt 不变，history 以 assistant/user 消息形式注入

**选择**：在 system prompt 和当前 user_input 之间插入历史消息，不改 system prompt。

**理由**：LLM 的 in-context learning 天然理解 user/assistant 交替消息。不需要额外 prompt 指令告诉 LLM "这是历史"。

## Risks / Trade-offs

**[Token 成本增加]** → 每轮 +200-500 tokens。通过截断为最近 4 条消息控制。如果 routing 使用独立小模型（如 gpt-4o-mini），成本增量可忽略。

**[History 暴露给 routing LLM]** → routing LLM 能看到最近 2 轮的完整对话内容。如果对话包含敏感信息，routing 模型的日志可能记录这些内容。缓解：routing 模型与主模型使用相同的安全策略。

**[ReAct loop 未被调用时 memory 仍不更新]** → 如果 routing 仍然判定 missing_slots（LLM 认为历史也不足以推断），提前返回仍然不写 memory。这是正确行为——此时确实缺少信息，需要用户澄清。

**[Keyword fallback 无历史]** → LLM 失败时 fallback 到 keyword 管线，keyword 无法做指代消解。但这是 fallback 路径的固有限制，可接受。
