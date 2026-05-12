## Why

Agent 在执行写操作后报错 `TypeError: 'in <string>' requires string as left operand, not dict`，导致用户看到不友好的错误输出。同时，HITL（Human-in-the-Loop）审批提示仅显示 `Approve? :`，缺乏操作说明、风险提示和输入引导，用户体验不足。这两个问题分别影响了系统的**正确性**和**可用性**。

## What Changes

- **修复类型错误**：在 `permission.py` 的 `_match_rules` 中，`params.get("url", "")` 可能返回非字符串类型，导致 `rule.domain not in url` 触发 `TypeError`。需要对参数值进行类型保护，确保 `in` 操作的两个操作数类型正确。同时在 `runtime.py` 后处理阶段增加类型安全检查，防止工具返回的 dict 结果被误用于字符串操作。
- **增强 HITL 审批提示 UX**：重构 `hitl.py` 的 `_ask_human` 方法，提供更丰富的审批交互体验：
  - 显示操作风险级别（WRITE / DANGEROUS）
  - 友好的操作描述（而非原始参数 dump）
  - 明确的输入选项引导：`[y]es / [n]o / [d]etail`
  - 适当的 summary 截断避免刷屏
  - 保证 Rich 格式化在非交互终端也能正确降级

## Capabilities

### New Capabilities
- `hitl-approval-ux`: 改进 HITL 审批提示的用户体验，包括风险展示、操作描述、输入引导和多级交互

### Modified Capabilities
- `permission-guard`: 增加参数类型保护，防止 dict/非字符串值导致 `in` 操作类型错误

## Impact

- **受影响文件**：`src/open_agent/safety/hitl.py`（审批交互）、`src/open_agent/safety/permission.py`（类型保护）、`src/open_agent/runtime.py`（后处理类型安全）
- **API 兼容性**：`HITLApprovalManager` 的公共接口 `approve()` 不变，变更仅限内部 `_ask_human` 方法和 `_match_rules` 的类型保护
- **依赖**：无新依赖，继续使用 `rich` 库
