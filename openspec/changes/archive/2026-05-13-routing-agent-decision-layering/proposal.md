## Why

当前路由层检测到 `missing_slots` 非空时会直接短路返回澄清问题，完全阻断 ReAct 循环。这导致一个关键体验问题：当用户说"帮我创建一个等差数列求和公式的代码"（未指定文件名），路由器判定 `missing_slots=["file_name", "language"]` 后直接拒绝，Agent 根本没有机会用 `task` 工具委派 sub-agent 去自行推断这些参数。路由层（只有分类能力）替 Agent（有工具感知能力）做了"该不该追问"的决策，职责越界。

行业最佳实践（LangChain RouterChain、OpenAI Assistants API、Semantic Kernel Planner）均遵循"路由负责理解，Agent 负责决策"的原则：路由层只做分类和参数提取，是否需要追问由下游 Agent 根据可用工具自主判断。

## What Changes

- **取消 `missing_slots` 短路机制**：删除 `runtime.py` 中基于 `missing_slots` 的 early return，改为将 `missing_slots` 作为 hint 注入 Agent 上下文，让 Agent 自主决定是追问用户还是直接用工具补全
- **引入 complexity 分层门控**：仅当 `complexity == "simple"` 且 `missing_slots` 非空时允许短路（简单任务确实缺关键信息就该问）；`medium` / `complex` 任务一律放行到 Agent
- **优化路由器 prompt 的 `missing_slots` 判定规则**：在统一路由器 system prompt 中增加"可推断性"指导——如果缺失参数可由 Agent 通过工具或常识合理推断，则不放入 `missing_slots`
- **确保路由调用 temperature=0.0**：当路由复用主 provider 时，在调用点强制覆盖 temperature 为 0，消除路由结果的不确定性

## Capabilities

### New Capabilities
- `routing-decision-handoff`: 路由与 Agent 的决策分层机制——定义 missing_slots 如何从"阻断信号"变为"上下文提示"，以及 complexity 分层门控规则

### Modified Capabilities
- `unified-llm-router`: 路由器 prompt 增加"可推断性"判断规则，减少对可由工具补全参数的过度标记
- `routing-runtime-integration`: 修改 runtime 中 missing_slots 的处理路径——从 early return 改为注入 Agent 上下文；增加 complexity 分层门控
- `intent-recognition`: Intent Parser 的 `missing_slots` 语义从"阻断必需"变为"建议补充"，由 Agent 决策层决定处理方式

## Impact

- **核心文件变更**: `runtime.py`（missing_slots 处理路径）、`unified.py`（路由 prompt）、`intent.py`（clarification 生成逻辑）
- **行为变更**: 用户输入信息不完整时，Agent 不再直接返回澄清问题，而是尝试用工具完成任务（体验提升）；仅简单任务+关键信息缺失时才追问
- **向后兼容**: 路由 JSON schema 不变（`missing_slots` 字段保留），只是 runtime 层的消费方式改变
- **无 breaking change**: 对外部 API 和 config 无影响
