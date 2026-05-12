## Why

当前框架的安全层采用**硬拦截**策略，导致三个系统性故障：
1. SafetyMiddleware 对 `web_search` 工具误检——搜索工具声明 `safety_checks=["url"]` 但参数中无 `url` 字段，SSRF 检查收到空字符串后报 "No hostname in URL"，搜索功能完全瘫痪。
2. CommandSafetyChecker 对管道符 `|`、`&&` 等 shell 基础元字符一刀切拦截，agent 无法使用 `curl | head` 等合法命令作为 web_search 故障的降级方案。
3. 安全层硬拦截后直接返回 `"Error: ..."` 字符串，不经过权限层/HITL，用户无法批准被误拦的操作，也不了解工具为何失败。

这三个问题在 web_search 不可用时形成了死循环：搜索工具被安全层误杀 → agent 尝试用 exec 降级 → exec 也被安全层拦截 → agent 退化输出无关内容。参照 Claude Code 的"权限提示而非硬拦截"路径重构安全-权限协作机制。

## What Changes

- **重构安全检查为参数感知模式**：安全检查绑定到具体的参数名（如 `param: "url"`），而非盲目查 `params["url"]`。内部构建 URL 的工具（如 DuckDuckGo 搜索）标记为跳过 URL 检查。
- **安全层从"硬拦截"变为"风险评估"**：SafetyMiddleware 不再直接返回错误字符串拦截执行，而是产出风险等级（safe/risky/blocked），传递给 PermissionMiddleware 决定是否需要用户确认。
- **元字符分级拦截**：将 `|`、`&&` 从"危险元字符"降级为"低风险元字符"，允许白名单命令使用管道，高风险操作（`$()`、反引号、`rm -rf`）仍硬拦截或需用户确认。
- **ReAct 循环增加工具健康度追踪**：连续 N 次失败的工具标记为 degraded，在 Observation 中提示 LLM 换用其他工具。
- **最终答案相关性守卫**：`_compose_final_answer()` 检测全步失败时返回结构化失败消息，而非返回无关的 `ls` 输出。

## Capabilities

### New Capabilities
- `safety-risk-escalation`: 安全层风险评估 + 权限层协作决策机制。SafetyMiddleware 产出风险等级而非硬拦截，PermissionMiddleware 根据风险等级决定放行/确认/拒绝，HITL 提示展示安全风险上下文。
- `tool-health-tracking`: ReAct 循环的工具健康度追踪。记录每个工具的连续失败次数，超过阈值后标记为 degraded 并在 Observation 中告知 LLM。
- `final-answer-guard`: 最终答案相关性守卫。当所有工具步骤均失败时，返回结构化失败消息（包含失败原因和建议），而非退化输出。

### Modified Capabilities
- `tool-web`: `web_search` 工具的 `safety_checks` 从 `["url"]` 改为空或标记 `internal: true`，因为搜索 URL 由库内部构建，无需 SSRF 检查。同时增加 `search_backend` 不可用时的结构化降级错误信息。
- `tool-shell`: CommandSafetyChecker 的元字符检测从一刀切改为三级分类（安全/低风险/高风险），低风险字符（`|`、`&&`）允许白名单命令使用。
- `execution-middleware-chain`: SafetyMiddleware 输出从 `"Error: ..."` 字符串改为结构化风险结果，PermissionMiddleware 接收风险等级并决定后续处理。
- `permission-guard`: PermissionMiddleware 需处理来自 SafetyMiddleware 的风险升级信号，对 `risky` 级别操作触发 HITL 确认而非直接放行。
- `hitl-approval-ux`: 审批提示新增安全风险上下文展示，包括被触发的安全规则名称和建议替代方案。

## Impact

- **核心代码**：`src/open_agent/safety/`（SafetyManager、CommandSafetyChecker、SSRFProtector）、`src/open_agent/middleware.py`（SafetyMiddleware、PermissionMiddleware）、`src/open_agent/agent/react.py`（健康度追踪、答案守卫）、`src/open_agent/tools/web.py`（safety_checks 声明）
- **配置**：`SafetyConfig` 可能需要新增字段（如元字符分级配置），`CommandSafetyChecker` 的 `_DANGEROUS_META_CHARS` 需拆分为多级列表
- **API 行为变化**：SafetyMiddleware 的返回值类型从 `str` 变为结构化对象，middleware chain 的接口需要适配
- **依赖**：无新增外部依赖
