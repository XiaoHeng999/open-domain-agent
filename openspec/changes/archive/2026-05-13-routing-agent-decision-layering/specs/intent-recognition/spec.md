## MODIFIED Requirements

### Requirement: Intent Parser
系统 SHALL 在 domain 内提取结构化 intent 和 slots。Intent Parser SHALL 输出 `missing_slots` 作为**建议补充信息**（而非阻断信号）。runtime 层 SHALL 根据 complexity 分层决定消费方式：simple 任务直接追问，medium/complex 任务注入 Agent 上下文。`generate_clarification()` 方法 SHALL 保留，仅在 simple 任务短路路径中使用。当有对话历史时，Intent Parser SHALL 能从历史上下文中推断出省略或指代的槽位值，而非仅依赖当前输入判定缺失。

#### Scenario: 完整 intent 提取
- **WHEN** 用户输入 "搜索2024年的财报数据"
- **THEN** Intent Parser 提取 intent="search_report"、slots={year: "2024", type: "财报"}、missing_slots=[]

#### Scenario: 参数缺失生成建议（非阻断）
- **WHEN** 用户输入 "帮我创建一个等差数列求和公式的代码"（未指定文件名）
- **THEN** Intent Parser 输出 missing_slots=["file_name"]，但不直接触发澄清
- **THEN** 由 runtime 根据 complexity 决定是追问还是注入上下文

#### Scenario: 从历史上下文推断省略槽位
- **WHEN** 对话历史中 assistant 曾返回 "2+2=4" 且用户输入 "再加100等于几？"
- **THEN** Intent Parser 提取 slots={base_number: 4, increment: 100}、missing_slots=[]
