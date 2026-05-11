## Why

当前路由系统（Complexity Judge → Domain Router → Intent Parser）三阶段均采用 keyword 子串匹配（`kw in text`），存在三个根本性缺陷：

1. **语义缺失** — "帮我看看代码哪有毛病" 无法匹配 "debug"/"fix" 关键词，路由到 general 而非 coding
2. **语言膨胀** — 每支持一种语言就要翻倍 keyword 表，且中英文混合场景频繁误匹配
3. **领域扩展成本 O(n)** — 每新增 domain/intent 就要手写 keyword + unit test，无法动态扩展

此外，路由结果在 runtime 中几乎未被消费：`skip_planning` 标志被计算但 PlanGenerator 从未被调用，`domain.system_prompt` 被计算但从未注入 prompt，`missing_slots` 澄清机制从未触发。

## What Changes

- 新增 **UnifiedLLMRouter**，用单次轻量模型调用（gpt-4o-mini / deepseek-chat）同时输出 complexity + domain + intent + slots，替代三阶段独立 keyword 匹配
- 将现有 keyword 逻辑 **降级为 offline fallback**（无 provider 时使用），不删除
- **BREAKING**: `RoutingPipeline` 的构造接口变更，新增可选 `routing_provider` 参数用于指定独立的轻量路由模型
- 修复 routing config 中 `domains` 字段从未传递到 DomainRouter 的 bug
- 修复 `intent.py` 中 "review" 关键词重复的 bug
- 将路由结果真正接入下游：`domain.system_prompt` 注入 ReAct prompt，`skip_planning` 控制是否调用 PlanGenerator，`missing_slots` 触发澄清流程

## Capabilities

### New Capabilities
- `unified-llm-router`: 单次 LLM 调用统一路由，一次输出 complexity + domain + intent + slots，替代三阶段 keyword 匹配
- `routing-runtime-integration`: 将路由结果真正接入 runtime 下游（prompt 注入、planning 控制、澄清流程）

### Modified Capabilities
- `intent-recognition`: 三阶段 keyword 路由降级为 fallback；主路径改为 unified LLM router；complexity 新增 medium 档位；clarification 流程实际接入 runtime
- `multi-agent-routing`: domain system_prompt 通过 routing 结果注入到 ReAct loop 的 prompt 中；`skip_planning` 真正控制 PlanGenerator 调用

## Impact

- **代码变更**：`routing/` 目录新增 `unified.py`；修改 `routing/router.py`、`runtime.py`、`config.py`、`agent/react.py`
- **配置变更**：`RoutingConfig` 新增 `routing_model` 字段（可选），允许路由使用独立于主模型的轻量模型
- **性能影响**：有 provider 时每次用户输入增加一次轻量 LLM 调用（~50-100ms, <$0.0001），但省去三阶段 keyword 匹配的维护成本
- **向后兼容**：无 provider 时完全退化为现有 keyword 逻辑，不破坏已有行为
- **测试影响**：现有 `test_routing.py` 全部保留（测试 fallback 路径），新增 unified router 测试
