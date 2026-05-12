## 1. 类型定义与配置

- [x] 1.1 创建 `src/open_agent/subagent/__init__.py`，导出 SubagentTool、SubagentManager、SubagentConfig
- [x] 1.2 创建 `src/open_agent/subagent/types.py`，定义 SubagentPreset、SubagentResult 数据类
- [x] 1.3 在 `config.py` 中添加 SubagentConfig Pydantic 模型（enabled, max_concurrent, max_children, default_max_turns, presets 字段），并在 AgentConfig 中新增 subagent 字段
- [x] 1.4 更新 `config.yaml` 添加 subagent 默认配置段

## 2. 预设类型系统

- [x] 2.1 创建 `src/open_agent/subagent/presets.py`，定义 BUILTIN_PRESETS 字典，包含 explore、plan、general 三个内置预设（system_prompt、allowed_tools、max_turns、description）
- [x] 2.2 实现 preset 合并逻辑：用户配置覆盖内置预设 + 支持新增自定义预设

## 3. SubagentManager 核心

- [x] 3.1 创建 `src/open_agent/subagent/manager.py`，实现 SubagentManager 类
- [x] 3.2 实现预设类型查找（preset lookup with "general" fallback）
- [x] 3.3 实现受限 ToolRegistry 构建（根据预设 allowed_tools 从父 ToolRegistry 筛选工具，排除 `task`）
- [x] 3.4 实现子代理 ReActLoop 实例创建（受限 registry + 预设 system_prompt + 独立 max_iterations）
- [x] 3.5 实现全局并发控制（max_concurrent + max_children 检查，asyncio.Semaphore 或条件等待）
- [x] 3.6 实现后台任务管理（asyncio.Task 创建、结果存储、agent_id 生成）
- [x] 3.7 实现级联终止（stop_all 方法，cancel 所有活跃 asyncio.Task，带超时等待）
- [x] 3.8 实现结果查询接口（get_result(agent_id) → status/answer/success/duration_ms）

## 4. SubagentTool 工具

- [x] 4.1 创建 `src/open_agent/subagent/tool.py`，实现 SubagentTool(Tool) 类
- [x] 4.2 定义工具参数 JSON Schema（prompt, subagent_type, description, run_in_background, max_turns）
- [x] 4.3 实现 execute() 同步路径：调用 manager 创建子代理 → 运行 ReActLoop → 返回 answer
- [x] 4.4 实现 execute() 异步路径：run_in_background=true 时启动 asyncio.Task → 立即返回 "[Started subagent: <id>]"
- [x] 4.5 实现执行追踪：在父 Trace 中创建 Span(kind=SUBAGENT)，记录 subagent_type、prompt、max_turns、success

## 5. Runtime 集成

- [x] 5.1 在 `runtime.py` 的 `on_start()` 中初始化 SubagentManager（传入 provider、tool_registry、config.subagent）
- [x] 5.2 在 `on_start()` 中创建 SubagentTool 并注册到 ToolRegistry
- [x] 5.3 在 `on_stop()` 中调用 SubagentManager.stop_all() 实现级联终止
- [x] 5.4 在 `trace.py` 的 SpanKind 枚举中添加 SUBAGENT 类型

## 6. 中间件适配

- [x] 6.1 更新 SafetyMiddleware 对 `task` 工具的放行逻辑（直接 pass-through）
- [x] 6.2 更新 PermissionMiddleware 对 `task` 工具的放行逻辑（直接 pass-through）

## 7. 测试

- [x] 7.1 创建 `tests/test_subagent.py`，测试 SubagentTool 参数定义和 schema 输出
- [x] 7.2 测试 SubagentManager 预设查找（正常 + fallback to general）
- [x] 7.3 测试受限 ToolRegistry 构建（explore 只含只读工具、排除 task）
- [x] 7.4 测试并发控制（超限等待 + 拒绝）
- [x] 7.5 测试级联终止（stop_all 取消所有活跃子代理）
- [x] 7.6 测试同步执行流程（mock provider → 验证返回 answer）
- [x] 7.7 测试异步执行流程（立即返回 + 后台结果存储）
- [x] 7.8 测试 Runtime 集成（on_start 注册 + on_stop 级联）
