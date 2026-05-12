## Context

当前系统在两个层面存在问题：

1. **类型安全问题**：`PermissionGuard._match_rules()` (permission.py:96) 中执行 `rule.domain not in url`，其中 `url = params.get("url", "")` 可能从 LLM 返回的工具参数中获取到 dict 而非 string。Python 的 `str.__contains__` 要求左操作数为 string，当 `rule.domain`（string）做 `in` 操作而右操作数是 dict 时不会报错，但反过来或其他变体场景会触发 `TypeError: 'in <string>' requires string as left operand, not dict`。同样，`runtime.py` 后处理阶段（metadata 构建、记忆写入等）对工具结果做字符串操作时也可能触发类似错误。

2. **HITL 审批 UX 问题**：`HITLApprovalManager._ask_human()` (hitl.py:120-129) 当前仅打印一行警告和 `Approve? [y/N]:`，缺乏：
   - 操作风险级别说明
   - 友好的操作描述（直接 dump 原始参数）
   - 输入选项引导（用户不知道可以输入什么）
   - 长参数的截断处理

现有相关模块：`PermissionMiddleware` → `PermissionGuard` → `HITLApprovalManager`，形成 middleware chain 中的权限决策管道。

## Goals / Non-Goals

**Goals:**
- 修复 `in` 操作类型不匹配导致的 `TypeError`
- 增强 HITL 审批提示的可读性和交互引导
- 保持 `HITLApprovalManager.approve()` 公共接口不变

**Non-Goals:**
- 不改变权限决策的四阶段管道架构
- 不引入新的交互方式（如 Web UI），仍基于 CLI/Rich
- 不修改 `_tool_messages` 消息格式

## Decisions

### Decision 1: 参数类型保护（防御式编程）

在 `_match_rules` 和其他使用 `params.get()` 值做 `in` 操作的地方，增加 `isinstance` 检查或 `str()` 转换。

**选择**：`str()` 转换而非抛出异常 — 因为 LLM 返回的参数格式不可控，防御式处理更稳健。

**替代方案**：在参数进入 middleware chain 前做统一 schema 校验 — 过度工程化，当前只需保护 `in` 操作。

### Decision 2: HITL 审批提示重构

将 `_ask_human` 的单行提示改为多行结构化提示：

```
⚠ [WRITE] 操作需要审批
─────────────────────────
操作: write_file
目标: /path/to/file
描述: 将创建/覆盖指定路径的文件

请选择: [y] 确认 / [n] 拒绝 / [d] 查看详情
> _
```

**选择**：结构化 Rich Panel 而非纯文本 — 利用已有的 Rich 依赖，提供更好的视觉层次。

**替代方案**：纯文本格式 — 不够醒目，用户体验差。

### Decision 3: summary 截断策略

对 `_build_summary` 中的参数值做截断，超过 100 字符的值用 `...` 替代。

**选择**：100 字符截断 — 足够显示关键信息，避免长 content 刷屏。

## Risks / Trade-offs

- **[风险] Rich 格式化在非 TTY 环境降级** → Rich Console 自动检测 TTY 并降级为纯文本，无需额外处理
- **[风险] `_ask_human` 变复杂后可维护性下降** → 将提示构建逻辑提取为 `_format_approval_prompt` 方法，保持 `_ask_human` 简洁
- **[权衡] `str()` 转换可能掩盖参数类型问题** → 加 `logger.debug` 记录类型不匹配情况，方便调试
