## MODIFIED Requirements

### Requirement: 内置预设类型 - Code Reviewer
系统 SHALL 提供内置的 "code-reviewer" 预设类型，专注于代码审查任务。

#### Scenario: Code Reviewer 只读工具集
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** 子代理的工具集 SHALL 仅包含：read_file, list_dir, search, web_search, web_fetch
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Code Reviewer 系统提示
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** 系统提示 SHALL 包含角色定义（资深代码审查专家）
- **THEN** 系统提示 SHALL 明确禁止修改文件
- **THEN** 系统提示 SHALL 指导子代理按以下审查维度逐项检查：
  1. **正确性**: 逻辑错误、边界条件、异常处理
  2. **安全性**: 注入攻击、敏感数据泄露、权限问题
  3. **性能**: 不必要的计算、资源泄漏、N+1 查询
  4. **可读性**: 命名、注释、代码组织
  5. **最佳实践**: 设计模式、DRY 原则、错误处理策略
- **THEN** 系统提示 SHALL 要求输出结构化审查报告：
  - 每个问题包含：严重程度（critical/high/medium/low）、文件路径和行号、问题描述、具体修复建议
  - 总结整体代码质量评分和改进优先级

#### Scenario: Code Reviewer 最大轮次
- **WHEN** 使用 subagent_type="code-reviewer" 创建子代理
- **THEN** max_turns SHALL 为 15

### Requirement: 内置预设类型 - Code Writer
系统 SHALL 提供内置的 "code-writer" 预设类型，专注于代码编写和修改任务。

#### Scenario: Code Writer 写入工具集
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：read_file, write_file, edit_file, list_dir, search, exec
- **THEN** 子代理 SHALL 不包含：task

#### Scenario: Code Writer 系统提示
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** 系统提示 SHALL 包含角色定义（专业代码编写专家）
- **THEN** 系统提示 SHALL 指导子代理遵循以下编码准则：
  1. **最小改动原则**: 只修改必要的代码，不做超出任务范围的改动
  2. **安全编码**: 避免 OWASP Top 10 漏洞（注入、XSS 等）
  3. **风格一致**: 保持与周围代码一致的命名、缩进和结构风格
  4. **充分验证**: 修改后使用 exec 运行测试或检查命令验证变更
- **THEN** 系统提示 SHALL 要求按以下工作流程操作：
  1. 阅读相关代码理解上下文
  2. 规划最小化修改方案
  3. 执行代码修改
  4. 运行验证（测试/lint/类型检查）
  5. 输出修改摘要（改了什么、为什么、验证结果）

#### Scenario: Code Writer 最大轮次
- **WHEN** 使用 subagent_type="code-writer" 创建子代理
- **THEN** max_turns SHALL 为 20
