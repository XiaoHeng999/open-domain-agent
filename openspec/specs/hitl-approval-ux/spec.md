## MODIFIED Requirements

### Requirement: 审批提示 SHALL 展示风险级别
HITL 审批提示 SHALL 在提示顶部显示操作的风险级别（WRITE / DANGEROUS / READ），使用视觉区分（如颜色、标签）让用户一眼识别风险。当审批由安全风险触发时，SHALL 额外展示安全风险上下文，包括被触发的安全规则名称和原始检查原因。

#### Scenario: 写操作审批提示显示风险级别
- **WHEN** 工具调用被分类为 WRITE 级别并触发人工审批
- **THEN** 审批提示 SHALL 显示 `[WRITE]` 标签，使用黄色（yellow）高亮

#### Scenario: 危险操作审批提示显示风险级别
- **WHEN** 工具调用被分类为 DANGEROUS 级别
- **THEN** 系统 SHALL 直接拒绝操作并显示 `[BLOCKED]` 标签，不触发人工审批

#### Scenario: 安全风险触发的审批提示显示安全上下文
- **WHEN** HITL 审批由 `risky` 级别的安全风险触发（如命令包含管道符）
- **THEN** 审批提示 SHALL 额外显示 `[SAFETY]` 标签和风险原因（如 "low-risk shell metacharacter: pipe operator"），使用橙色（orange）高亮

### Requirement: 审批提示 SHALL 展示友好的操作描述
HITL 审批提示 SHALL 将原始参数转换为人类可读的描述，包括操作名称、目标路径/URL，而非直接 dump 完整参数字典。

#### Scenario: 写文件操作的描述
- **WHEN** 触发 `write_file` 工具的审批提示
- **THEN** 提示 SHALL 显示操作名称 `write_file` 和目标路径，参数值超过 100 字符时 SHALL 截断并添加 `...`

#### Scenario: Shell 命令操作的描述
- **WHEN** 触发 `exec` 工具的审批提示
- **THEN** 提示 SHALL 显示操作名称 `exec` 和待执行的命令内容

#### Scenario: 安全风险审批提示的描述
- **WHEN** 安全风险触发的审批提示
- **THEN** 提示 SHALL 显示工具名称、被拦截的命令/URL、触发的安全规则和建议替代方案（如 "Consider using web_search instead of curl"）

### Requirement: 审批提示 SHALL 提供明确的输入引导
HITL 审批提示 SHALL 明确列出用户可选的输入选项，包括确认、拒绝和查看详情。

#### Scenario: 用户输入 yes 确认操作
- **WHEN** 审批提示展示后，用户输入 `y` 或 `yes`
- **THEN** 操作 SHALL 被批准，返回 `approved=True`

#### Scenario: 用户输入 no 拒绝操作
- **WHEN** 审批提示展示后，用户输入 `n` 或 `no` 或直接回车
- **THEN** 操作 SHALL 被拒绝，返回 `approved=False`

#### Scenario: 用户输入 detail 查看详情
- **WHEN** 审批提示展示后，用户输入 `d` 或 `detail`
- **THEN** 系统 SHALL 显示完整的操作参数，然后重新展示审批提示

#### Scenario: 非交互环境默认拒绝
- **WHEN** HITL 运行在非交互模式（`interactive=False`）或非 TTY 环境
- **THEN** 写操作 SHALL 默认被拒绝，不展示任何提示

### Requirement: 审批提示 SHALL 在非 TTY 环境正确降级
当终端不支持 Rich 格式化时，审批提示 SHALL 降级为纯文本格式，仍包含风险级别、操作描述和输入引导。

#### Scenario: 无 TTY 支持的环境
- **WHEN** Rich Console 检测到非 TTY 环境
- **THEN** 审批提示 SHALL 以纯文本形式展示，保留所有关键信息（风险级别、操作、选项引导）
