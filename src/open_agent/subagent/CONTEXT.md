# subagent/ — 子 Agent 管理

- `manager.py` — SubagentManager：生命周期、并发控制（信号量）、级联停止
- `presets.py` — 5 个内置预设（explore/plan/code-reviewer/code-writer/researcher）+ 用户自定义合并
- `types.py` — SubagentPreset / SubagentResult 数据类型
- `tool.py` — SubagentTool：将子 agent 暴露为可调用的 task 工具
