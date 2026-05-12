## 1. P0 崩溃级 Bug 修复

- [x] 1.1 修复 `base.py` BaseComponent 类变量共享：将 `_registered`/`_started` 从类变量改为 `__init__` 中的实例变量，确保所有子类调用 `super().__init__()`
- [x] 1.2 修复 `runtime.py:396-403` `_tool_messages` 类型混淆：将 `s.action.tool_name` 改为正确的 dict 访问 `block["name"]`，确保异常路径不崩溃
- [x] 1.3 修复 `react.py:616-618` domain system prompt 重复拼接：删除重复的 `self._domain_system_prompt + "\n\n" + system_content` 行
- [x] 1.4 修复 `mcp_integration.py:407` `entry.server_id` 属性不存在：改用 `getattr(entry, "_server_id", None)` 并处理 None 情况

## 2. P1 多 Tool Use 支持

- [x] 2.1 重构 `react.py` `_think_and_act` 返回 `list[Action]` 而非单个 `Action`，处理 LLM 返回的多个 tool_use block
- [x] 2.2 修改 `react.py` `run()` 主循环：遍历 action 列表，为每个 action 调用 `_execute_action`，构建完整的 tool_result 消息对
- [x] 2.3 更新 `react.py` 重复检测逻辑：从单个 action_key 改为跟踪 action_key 列表，检测整个 action batch 的重复
- [x] 2.4 更新 `react.py` end_turn 检测：仅在 tool_calls 为空列表时触发直接回答路径

## 3. P1 安全加固

- [x] 3.1 修复 `safety/command.py` 白名单绕过：添加 shell 元字符检测（`;`, `|`, `&&`, `||`, `$()`, backtick, `>`, `<`），在白名单模式前先检测危险元字符
- [x] 3.2 修复 `mcp_integration.py:109` stdio 命令解析：将 `command.split()` 替换为 `shlex.split(command)`
- [x] 3.3 修复 `mcp_integration.py` HTTP transport 连接池：将 httpx.AsyncClient 提升为实例变量，在 `connect()` 时创建，`disconnect()` 时关闭
- [x] 3.4 修复 `mcp_integration.py` `_request_counter` 并发安全：改用 `itertools.count()` 或在类级别使用 `asyncio.Lock`

## 4. P1 Recovery 安全管道集成

- [x] 4.1 定义 `ExecutionMiddleware` 协议类（`async def process(name, params, context, next)`）和 `MiddlewareContext` 数据类
- [x] 4.2 实现 `SafetyMiddleware`：封装 `_run_safety_checks` 逻辑
- [x] 4.3 实现 `PermissionMiddleware`：封装 permission guard 检查逻辑
- [x] 4.4 实现 `ExecuteMiddleware`：封装实际工具调用逻辑
- [x] 4.5 实现 `TruncateMiddleware`：封装结果截断逻辑
- [x] 4.6 重构 `ToolRegistry.execute()` 使用 middleware chain，保持返回值和行为兼容
- [x] 4.7 修改 `recovery/strategies.py` 所有策略：将 `tool_handler(**args)` 替换为 `tool_registry.execute(tool_name, args)`，确保重试经过完整管道

## 5. P2 架构改进

- [x] 5.1 为 `RuntimeMemory` 添加 `reset_task_state()` 公开方法，移除 `react.py:204` 的 `_task_state` 直接赋值
- [x] 5.2 修复 `runtime.py` sandbox 初始化时序：将 `sandbox.on_start()` 从 `create_task` 改为 `await` 同步等待
- [x] 5.3 修复 `model.py` OpenAI/Anthropic Provider 对 None content 的处理：添加 `or ""` 防护
- [x] 5.4 修复 `retrieval.py:108` `allow_pickle=True` 安全风险：改用 `np.load(path, allow_pickle=False)` 或使用更安全的序列化格式
- [x] 5.5 修复 `retrieval.py:225` `__import__("time")` 反模式：改为使用模块顶部的 `import time`

## 6. 测试覆盖

- [x] 6.1 添加 P0 修复的回归测试：BaseComponent 独立状态、_tool_messages 类型、prompt 重复、server_id 属性
- [x] 6.2 添加多 tool_use 执行的单元测试：2 个 tool call、1 个失败、0 个 tool call
- [x] 6.3 添加安全加固的回归测试：命令注入绕过、shlex.split 路径参数、HTTP 连接复用
- [x] 6.4 添加 middleware chain 测试：每个 middleware 独立测试、完整链路测试、recovery 经过管道测试
