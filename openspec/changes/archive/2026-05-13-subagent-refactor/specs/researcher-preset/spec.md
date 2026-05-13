## ADDED Requirements

### Requirement: 内置预设类型 - Researcher
系统 SHALL 提供内置的 "researcher" 预设类型，专注于 Web 信息搜索、文档查阅和知识整合分析。

#### Scenario: Researcher 只读工具集
- **WHEN** 使用 subagent_type="researcher" 创建子代理
- **THEN** 子代理的工具集 SHALL 包含：web_search, web_fetch, search, read_file, list_dir
- **THEN** 子代理 SHALL 不包含：write_file, edit_file, exec, task

#### Scenario: Researcher 系统提示结构
- **WHEN** 使用 subagent_type="researcher" 创建子代理
- **THEN** 系统提示 SHALL 包含角色定义（信息研究专家）
- **THEN** 系统提示 SHALL 明确禁止修改文件或执行命令
- **THEN** 系统提示 SHALL 要求对信息来源进行标注
- **THEN** 系统提示 SHALL 要求输出结构化的研究报告（摘要、关键发现、来源列表）

#### Scenario: Researcher 最大轮次
- **WHEN** 使用 subagent_type="researcher" 创建子代理
- **THEN** max_turns SHALL 为 25

#### Scenario: Researcher 工作流程指导
- **WHEN** researcher 子代理接收到研究任务
- **THEN** 系统提示 SHALL 指导子代理按以下步骤工作：
  1. 分析研究问题，拆解关键信息需求
  2. 使用 web_search 搜索相关资源
  3. 使用 web_fetch 深入阅读关键页面
  4. 使用 search/read_file 查阅本地文档
  5. 整合分析，输出结构化报告
