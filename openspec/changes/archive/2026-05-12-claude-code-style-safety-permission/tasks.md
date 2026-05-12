## 1. SafetyCheckResult 风险分级

- [x] 1.1 在 `SafetyCheckResult` dataclass 中新增 `risk_level` 字段（默认 `None`，取值 `"safe"` / `"risky"` / `"blocked"`），并更新 `to_dict()` 方法
- [x] 1.2 将 `_DANGEROUS_METACHAR_PATTERNS` 拆分为 `_LOW_RISK_METACHAR_PATTERNS`（`|`、`&&`、`||`）和 `_HIGH_RISK_METACHAR_PATTERNS`（`;`、`$(`、反引号、`>`、`<`）
- [x] 1.3 修改 `CommandSafetyChecker.check()` 返回 `risk_level`：低风险元字符返回 `risky`，高风险元字符和黑名单模式返回 `blocked`，安全返回 `safe`
- [x] 1.4 修改 `SSRFProtector.check_url()` 返回 `risk_level`：云元数据端点和内网 IP 返回 `blocked`，合法 URL 返回 `safe`
- [x] 1.5 修改 `PathRestrictor.check_path()` 返回 `risk_level`：路径穿越返回 `blocked`，合法路径返回 `safe`

## 2. SafetyMiddleware 参数感知与风险传递

- [x] 2.1 新增 `SafetyRisk` dataclass（`tool_name`、`check_type`、`reason`、`risk_level`、`matched_pattern`）
- [x] 2.2 在 `MiddlewareContext` 中新增 `safety_risks: list[SafetyRisk]` 字段（默认空列表）
- [x] 2.3 修改 `Tool` 基类的 `safety_checks` 字段支持映射语法：纯字符串 `"url"` 等价于 `{"type": "url", "param": "url"}`，显式映射 `{"type": "url", "param": "target_url"}`
- [x] 2.4 重写 `SafetyMiddleware.process()`：解析参数绑定，`blocked` 级别短路返回错误字符串，`risky` 级别附加到 `context.safety_risks` 后调用 `next()`，检查参数不存在时跳过该检查

## 3. web_search 工具安全配置修复

- [x] 3.1 将 `DuckDuckGoSearchTool` 和 `BraveSearchTool` 的 `safety_checks` 从 `["url"]` 改为 `[]`，因为搜索 URL 由库内部构建不需要 SSRF 检查
- [x] 3.2 验证修改后 `web_search` 不再触发 "No hostname in URL" 错误

## 4. PermissionMiddleware 安全风险协作

- [x] 4.1 修改 `PermissionMiddleware.process()` 检查 `context.safety_risks`，当存在 `risky` 级别的 SafetyRisk 且权限模式非 unrestricted 时，触发 HITL 确认
- [x] 4.2 修改 HITL 审批调用，传入安全风险上下文（`SafetyRisk` 对象），使审批提示能展示安全规则名称和风险原因

## 5. HITL 审批提示安全上下文展示

- [x] 5.1 修改 `HITLApprovalManager.approve()` 接受可选的 `safety_risks` 参数
- [x] 5.2 在审批提示中新增 `[SAFETY]` 标签显示安全风险原因，使用橙色高亮
- [x] 5.3 在审批提示的操作描述中展示触发的安全规则和建议替代方案

## 6. ReAct 循环工具健康度追踪

- [x] 6.1 在 `ReActLoop.run()` 中初始化 `tool_failure_counts: dict[str, int]` 和 `degraded_tools: set[str]`
- [x] 6.2 在每次工具执行后更新计数：失败递增，成功重置为 0 并从 `degraded_tools` 移除
- [x] 6.3 当连续失败次数 ≥ 3 时将工具加入 `degraded_tools`，并在 Observation content 末尾追加 degraded 警告
- [x] 6.4 当所有被调用的工具都已 degraded 时，强制终止循环并设置失败消息

## 7. 最终答案相关性守卫

- [x] 7.1 修改 `_compose_final_answer()` 新增全失败检测：无成功步骤时返回结构化失败消息（包含工具名和最后错误原因）
- [x] 7.2 新增无关成功检测：仅无关工具成功时返回包含失败信息和附带说明的消息

## 8. 测试验证

- [x] 8.1 编写 `test_command_safety_risk_levels` 测试：验证 `safe` / `risky` / `blocked` 三级分类正确性
- [x] 8.2 编写 `test_safety_middleware_risk_escalation` 测试：验证 `risky` 不短路而是传递到 PermissionMiddleware
- [x] 8.3 编写 `test_web_search_no_url_check` 测试：验证搜索工具不再触发 URL 安全检查
- [x] 8.4 编写 `test_permission_middleware_risky_handling` 测试：验证 PermissionMiddleware 对 risky 操作触发 HITL
- [x] 8.5 编写 `test_tool_health_tracking` 测试：验证连续失败计数和 degraded 标记
- [x] 8.6 编写 `test_final_answer_guard` 测试：验证全失败和无关成功场景的返回消息
- [x] 8.7 端到端验证：运行之前失败的搜索场景，确认 agent 能成功完成搜索或返回有意义的失败消息
