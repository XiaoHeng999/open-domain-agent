## Context

当前路由系统采用三阶段独立 keyword 匹配管线（`ComplexityJudge` → `DomainRouter` → `IntentParser`），每阶段各自维护 keyword 表。路由结果在 `AgentRuntime.run()` 中生成后，仅有 `domain.domain` 被用于 skill matching，其余字段（complexity、system_prompt、skip_planning、missing_slots）均未被消费。

现有 provider 接口支持 OpenAI / Anthropic / DeepSeek / Local 四种后端，`complete_structured` 方法可返回 JSON 结构化输出。`RoutingConfig` 已定义 `complexity_method` 字段但 `domains` 字段从未传递到 `DomainRouter`。

## Goals / Non-Goals

**Goals:**
- 用单次轻量 LLM 调用替代三阶段 keyword 匹配，一次输出 complexity + domain + intent + slots
- 保留 keyword 逻辑作为无 provider 时的 offline fallback
- 将路由结果真正接入 runtime：prompt 注入、planning 控制、澄清流程
- 修复已知 bug：domains config 未传递、intent.py 重复关键词
- 支持配置独立的轻量路由模型（与主 ReAct 模型解耦）

**Non-Goals:**
- 不重新设计 provider 接口或新增 provider
- 不删除现有 keyword-based 类（仅降级为 fallback）
- 不引入 embedding 模型或向量检索
- 不实现 multi-domain 路由（单次请求只路由到一个 domain）
- 不改动 skill matching 的匹配逻辑

## Decisions

### Decision 1: 单次 LLM 调用 vs 三次独立调用

**选择：单次调用**

三个阶段本质上是同一个分类问题——"理解用户想干什么"。拆成三次调用会导致：
- 延迟 3x（每次 ~50-100ms）
- 成本 3x
- 上下文割裂——domain 判断不知道 complexity，intent 判断不知道 domain 的置信度

单次调用让模型在完整上下文下同时输出所有字段，一次完成。

### Decision 2: 路由模型独立配置

**选择：新增 `routing_model` 可选配置**

在 `RoutingConfig` 中新增 `routing_provider` / `routing_name` / `routing_api_key` / `routing_base_url` 字段，允许用户为路由指定更便宜的模型（如 gpt-4o-mini、deepseek-chat）。不指定时复用主模型配置。

**替代方案**：为路由创建独立 provider 实例——增加了实例管理复杂度，且路由调用量远小于 ReAct 循环，复用配置更简单。

### Decision 3: Fallback 策略

**选择：LLM 失败时 fallback 到 keyword，keyword 逻辑原样保留**

- 有 provider → 走 unified LLM router
- LLM 调用异常 → fallback 到现有三阶段 keyword pipeline
- 无 provider → 直接走 keyword pipeline

这样保证离线场景和测试环境仍然可用。

### Decision 4: routing 结果接入 runtime

**选择：分三个接入点**

1. **prompt 注入**：`routing_decision.domain.system_prompt` 传入 `PromptBuilder`，作为 system prompt 的一部分
2. **planning 控制**：`routing_decision.skip_planning == False` 时调用 `PlanGenerator.generate()`，结果注入 ReAct loop 的 context
3. **澄清流程**：`routing_decision.intent.missing_slots` 非空时，直接返回澄清问题给用户，不进入 ReAct loop

### Decision 5: UnifiedLLMRouter 的 prompt 设计

**选择：领域描述 + few-shot 示例的 system prompt**

```
系统 prompt 结构：
1. 角色定义（请求分类器）
2. 可用 domains 列表及描述
3. 各 domain 的典型 intent 列表
4. 复杂度分级规则（simple/medium/complex）
5. 输出 JSON schema
6. 2-3 个 few-shot 示例（中英文各一个）
```

domains 描述从 `DomainRouter._domains` 动态读取，新增 domain 自动生效。

## Risks / Trade-offs

- **[延迟增加]** → 每次用户输入增加一次 LLM 调用（~50-100ms）。缓解：使用轻量模型（gpt-4o-mini）并设置低 `max_tokens`（200）；routing 结果可缓存相似 query
- **[LLM 输出格式不稳定]** → JSON 解析失败概率。缓解：已有 `complete_structured` 的 JSON 修复逻辑；失败时 fallback 到 keyword
- **[路由模型成本]** → 每 1000 次请求约 $0.01-0.05。缓解：相比 keyword 的维护人力成本，可忽略
- **[中英文混合场景]** → prompt 中包含中英文 few-shot 示例，确保模型对两种语言都能正确分类
