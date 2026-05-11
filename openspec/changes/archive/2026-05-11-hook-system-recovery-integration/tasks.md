## 1. Hook 模块基础结构

- [x] 1.1 创建 `src/open_agent/hooks/__init__.py`，定义公共 API（导出 HookEvent, HookResult, HookManager）
- [x] 1.2 创建 `src/open_agent/hooks/types.py`，实现 HookEvent 枚举（SESSION_START, TOOL_BEFORE, TOOL_AFTER）、HookResult dataclass（content, blocked, metadata）
- [x] 1.3 创建 `src/open_agent/hooks/manager.py`，实现 HookManager 类：register(event, callback, priority) 注册、fire(event, context) 按优先级触发、blocked 中断逻辑

## 2. 内置 Hook 实现

- [x] 2.1 创建 `src/open_agent/hooks/builtin.py`，实现 welcome_hook：打印 HELLO! LUCKY! 字符图案到终端，返回 HookResult(content=简化文本)
- [x] 2.2 实现 pre_check_hook：对高风险工具（ExecTool）检查危险命令模式，匹配时返回 blocked=True
- [x] 2.3 实现 audit_hook：记录 tool_name、success、duration_ms 到 logger，返回 HookResult(content=审计摘要)

## 3. Hook 接入 ReAct 循环

- [x] 3.1 在 ReActLoop.__init__ 中新增可选参数 hook_manager: HookManager | None = None
- [x] 3.2 修改 _execute_action()：工具执行前调用 hook_manager.fire(TOOL_BEFORE, context)，检查 blocked
- [x] 3.3 修改 _execute_action()：工具执行后调用 hook_manager.fire(TOOL_AFTER, context)，将 content 注入 tool_result message

## 4. Recovery 系统接入 ReAct 循环

- [x] 4.1 修改 _execute_action() 的 except ToolError 分支：调用 execute_recovery_chain(error, context)
- [x] 4.2 恢复成功时：用恢复结果替换 content，设置 success=True
- [x] 4.3 恢复失败时：保留错误信息并附加恢复 trace 摘要，success=False

## 5. Runtime 集成与配置

- [x] 5.1 在 AgentConfig 中添加 HooksConfig 配置块（enabled 默认 True，welcome_enabled 默认 True）
- [x] 5.2 修改 AgentRuntime.on_start()：创建 HookManager，注册三个内置 Hook，赋值给 react_loop._hook_manager
- [x] 5.3 修改 AgentRuntime.on_start()：触发 SESSION_START 事件，将欢迎信息注入 system prompt

## 6. 测试

- [x] 6.1 编写 tests/test_hooks.py：HookManager 注册/触发/blocked/优先级排序测试
- [x] 6.2 编写测试验证 welcome_hook 输出 HELLO! LUCKY! 图案
- [x] 6.3 编写测试验证 pre_check_hook 阻止危险命令
- [x] 6.4 编写测试验证 audit_hook 记录日志
- [x] 6.5 编写测试验证 recovery 接入：ToolError 触发恢复链、恢复成功/失败场景
- [x] 6.6 运行完整测试套件确认无回归
