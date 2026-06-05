# safety/ — 安全系统

- `__init__.py` — SafetyManager：统一门面，3 级（strict/permissive/off）
- `command.py` — CommandSafetyChecker：黑名单 + 高危字符 + 白名单模式
- `ssrf.py` — SSRFProtector：私有 IP + 云元数据 + DNS rebinding 防御
- `workspace.py` — PathRestrictor：工作空间边界 + 敏感文件保护
- `permission.py` — PermissionGuard：4 阶段决策管道（deny → mode → allow → ask）
- `hitl.py` — HITLApprovalManager：3 级人机审批（Read 自动 / Write 确认 / Dangerous 阻断）
