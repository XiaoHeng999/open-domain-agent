# tools/ — 内置工具

- `base.py` — Tool ABC + FunctionTool 适配器，含参数类型转换和 JSON Schema 验证
- `filesystem.py` — read_file / write_file / edit_file / list_dir
- `shell.py` — exec：异步子进程或沙箱执行
- `web.py` — web_search（DuckDuckGo/Brave）+ web_fetch（HTML→Markdown）
- `todo.py` — todo：会话任务计划管理
- `subagent.py` — task：子 agent 调用入口
- `mcp_client.py` — mcp_client：运行时 MCP 服务器管理
- `sandbox_control.py` — sandbox_control：沙箱生命周期控制
- `self.py` — self：运行时状态检查和动态配置
- `search.py` — search：代码搜索工具
