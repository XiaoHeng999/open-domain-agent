## Context

当前 `runtime.py` 中路由层与 Agent 层的职责边界不清晰。路由管线（UnifiedLLMRouter + keyword fallback）负责分类、提取 slots、识别 missing_slots，但 runtime 在消费路由结果时，一旦 `missing_slots` 非空就直接返回澄清问题（`runtime.py:360-372`），完全跳过 ReAct 循环。

这导致一个具体问题：用户说"帮我创建一个等差数列求和公式的代码"（未指定文件名），路由器标记 `missing_slots=["file_name", "language"]` 后短路，Agent 没机会用 `task` 工具委托 sub-agent 自行决定文件名。加上 "sum.py" 后 `missing_slots` 为空，Agent 正常工作。

此外，当 `config.yaml` 未配置 `routing_provider` 时，路由复用主 provider（temperature=0.7），增加了路由结果的波动性。

## Goals / Non-Goals

**Goals:**
- 路由层只负责"理解"（分类、参数提取），不负责"决策"（是否追问用户）
- Agent 层基于工具感知能力自主决定：是追问用户还是用工具补全缺失信息
- 简单任务（问候、单步事实问答）信息确实缺失时，仍可快速追问，不浪费 Agent 循环
- 路由结果稳定可复现（temperature=0.0）

**Non-Goals:**
- 不重构路由管线的整体架构（UnifiedLLMRouter + keyword fallback 结构保持不变）
- 不引入新的 slot filling 对话循环机制（由 Agent 的 ReAct 循环自然处理）
- 不修改 `missing_slots` 的 JSON schema（字段保留，语义从"阻断"变为"建议"）

## Decisions

### Decision 1: missing_slots 从 early return 改为上下文注入

**选择**: 删除 `runtime.py:360-372` 的短路返回，改为将 `missing_slots` 构造为一条 context hint 消息注入 Agent 的消息列表。

**替代方案**:
- A) 完全忽略 missing_slots → 丢失了路由层的信息提取能力，Agent 可能在信息不足时盲目执行
- B) 保留短路但加白名单（哪些 slot 可以忽略）→ 维护成本高，每种工具都要配置
- C) 将 missing_slots 注入上下文 → **选中**。保留路由信息，决策权交给 Agent

**实现方式**: 在构造 Agent 消息时，如果 `missing_slots` 非空，追加一条 system 级别的 hint：
> "路由层检测到以下参数可能缺失: {slot_list}。如果可以通过工具或常识合理推断，请直接执行任务。"

### Decision 2: Complexity 分层门控

**选择**: 仅当 `complexity == "simple"` 且 `missing_slots` 非空时才允许短路返回。

**替代方案**:
- A) 完全取消短路 → 简单任务（如"今天天气"没给城市）也会进入 Agent 循环再追问，增加延迟
- B) 按缺失 slot 数量门控 → 难以设定合理阈值
- C) 按 complexity 分层 → **选中**。simple 任务缺参数确实该问；medium/complex 任务 Agent 可以规划和补全

**实现方式**: 修改 `runtime.py` 的条件为：
```python
if (routing_decision.intent.missing_slots
    and routing_decision.complexity.complexity == "simple"):
```

### Decision 3: 路由 prompt 增加"可推断性"判断

**选择**: 在 unified.py 的 system prompt 中增加规则：如果缺失参数可由 Agent 通过工具或常识合理推断，则 `missing_slots` 置空。

**理由**: 即使 Agent 可以自行处理，减少不必要的 missing_slots 标记也能减轻 Agent 上下文的噪音。这是源头治理。

**实现方式**: 在 `_SYSTEM_PROMPT_TEMPLATE` 的规则部分追加：
> "仅当参数完全无法推断且任务无法执行时才标记 missing_slots。如果参数可通过工具自动决定（如文件名、编程语言），视为可推断，不放入 missing_slots。"

### Decision 4: 强制路由 temperature=0.0

**选择**: 当路由复用主 provider 时，在 UnifiedLLMRouter 的 `route()` 调用点显式传入 `temperature=0.0` override。

**替代方案**:
- A) 要求用户必须配置 routing_provider → 增加配置负担
- B) 在 provider 层面做 temperature override → 侵入性太强
- C) 在路由调用点传 temperature override → **选中**。最小侵入

**实现方式**: 检查 `UnifiedLLMRouter.route()` 方法中调用 `self._provider.complete()` 的地方，确保传入 `temperature=0.0`。

## Risks / Trade-offs

- [Risk] Agent 可能忽略 missing_slots hint，在真正需要追问时也不问 → **Mitigation**: prompt 中明确指导"如果确实无法推断，请向用户追问"；后续可通过 agent-evaluation 量化评估
- [Risk] 简单任务的短路判断依赖 complexity 分类准确性 → **Mitigation**: 现有 complexity 分类已有较高准确度；且简单任务即使误放行也只是多一轮对话
- [Risk] 路由 prompt 的"可推断性"规则依赖 LLM 理解能力，不同模型效果可能不同 → **Mitigation**: 这是一个补充优化，核心保障在 Decision 1 和 2
- [Trade-off] 复杂任务信息不完整时不再第一时间追问，而是先尝试执行 → 这是预期行为：宁可多执行一步再追问，也不要过早阻断

## Open Questions

- 无。四个 Decision 的边界条件已在 proposal 和 specs 中通过 scenario 覆盖。
