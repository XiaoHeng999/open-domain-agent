# CLAUDE.md — open-agent 项目指南

> 本文件是 AI 编程助手的**路由器**，不是百科全书。详细信息见 `docs/` 下的主题文档。

## 项目概述

open-agent 是基于 Harness Engineering 原则的开源 coding agent 框架。提供 ReAct 循环、多级路由、分层记忆、安全沙箱、错误恢复、子 agent 等完整能力。

## 技术栈

- **语言**: Python 3.11+, 全面 async/await
- **核心依赖**: Pydantic v2, Typer CLI, Rich, httpx, PyYAML
- **可选依赖**: OpenAI SDK / Anthropic SDK / DeepSeek (via OpenAI) / Docker / Daytona SDK
- **测试**: pytest + pytest-asyncio (asyncio_mode=auto)
- **构建**: hatchling, CLI 入口 `agent` → `open_agent.cli:app`

## 快速开始

```bash
# 安装（开发模式 + 常用 provider）
uv pip install -e ".[dev,openai,anthropic]"

# 运行测试
pytest tests/ -x -q

# 运行全部验证
make check

# 启动 agent
agent run "你的任务"
agent chat  # 交互模式
```

## 硬约束

1. **新工具必须继承 Tool ABC** — 见 `src/open_agent/tools/base.py`，实现 `name`/`description`/`parameters`/`execute()`
2. **新组件必须有生命周期** — 继承 `BaseComponent`，实现 `on_start()`/`on_stop()`
3. **中间件链顺序不可变** — Safety → Permission → Execute → OutputValidation → Truncate
4. **安全检查不可绕过** — SafetyMiddleware 必须在 ExecuteMiddleware 之前
5. **异步优先** — 所有新 IO 操作必须用 async def
6. **错误类型必须挂载到层级** — 继承 `errors.py` 中的对应类（`ToolError`/`AgentError`/`SecurityError`）
7. **配置项必须加到 config.py** — 使用 Pydantic v2 BaseModel，支持 env var 覆盖
8. **所有 public API 必须有 type hints** — 使用 `from __future__ import annotations`
9. **测试必须通过才能 commit** — `pytest tests/ -x` 不允许有 failure
10. **不在 ABC 方法上做 breaking change** — 新方法提供默认实现
11. **工具 schema 用 JSON Schema** — 参见 `Tool.parameters` 属性
12. **中文/英文双语支持** — 路由关键词和提示模板覆盖中英文

## 架构文档索引

| 主题 | 文件 | 内容 |
| 整体架构 | [docs/architecture.md](docs/architecture.md) | 组件关系、数据流、关键决策 |
| 添加工具 | [docs/adding-tools.md](docs/adding-tools.md) | Tool ABC 继承、注册、测试 |
| 添加恢复策略 | [docs/adding-recovery.md](docs/adding-recovery.md) | RecoveryStrategy 接口、链注册 |
| 添加中间件 | [docs/adding-middleware.md](docs/adding-middleware.md) | Middleware 协议、管道扩展 |
| 测试规范 | [docs/testing-guide.md](docs/testing-guide.md) | 测试约定、fixture、mock 策略 |
| Harness 设计 | [docs/harness-design.md](docs/harness-design.md) | Harness Engineering 决策记录 |

## 会话结束流程

1. 运行 `make check` 确认一切通过
2. 提交变更（每个逻辑操作一个 commit）
3. 更新相关文档（如有架构变更需同步 docs/）
