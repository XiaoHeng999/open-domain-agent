# PRD: Codebase Health — 缺陷修复、死代码清理与功能补全

## Problem Statement

经过对 73 个源文件、83 个测试文件的全面审查，发现代码库存在以下四类问题：

1. **运行时崩溃风险** — 幽灵导出（`TokenEstimator`）、`LocalProvider` 缺少关键方法、`MemoryError` 遮蔽内置异常、Sandbox 同步阻塞事件循环
2. **功能失效** — Memory tracing 全部失效、语义搜索 stub 永远返回空、恢复策略的 fallback 查找永远为空、`skill` CLI 命令是空壳、`OutputValidationMiddleware` 误判合法空输出
3. **代码腐化** — 大量死代码（向后兼容层、未接入模块、废弃 ABC）、`SubagentTool` 双实现、`complete_structured` 标记废弃但被 8+ 处调用、SQLite 并发无保护、私有属性被外部访问
4. **测试基础设施薄弱** — 无 conftest.py、无覆盖率配置、fixture 大量重复、存在空壳测试

这些问题不是孤立的：死代码增加维护负担并掩盖真实 bug，静默吞异常使问题难以诊断，功能失效意味着用户花钱买了不工作的特性。

## Solution

按优先级分三波修复：

**P0 — 阻断性缺陷**（必须先修，否则后续改动可能建在沙上）：
- 修复幽灵导出和命名冲突
- 修复 Sandbox 事件循环阻塞
- 删除不可用的 `LocalProvider`

**P1 — 功能失效与代码腐化**（核心改动）：
- 修复 Memory tracing、空输出误判、skill CLI
- 完成 `complete_structured` → `complete_with_tools` 迁移
- 统一 `SubagentTool` 为单一实现
- 清理全部死代码
- 修复恢复策略无效路径

**P2 — 测试基础设施**（收尾）：
- 创建共享 conftest.py
- 添加覆盖率配置
- 删除空壳测试

同时在 CLI chat 界面中增加 token 用量实时显示（每次回复 token 数、累计 token 数、prompt 前剩余 budget）。

## User Stories

### Token 可观测性

1. 作为用户，我希望在每次 agent 回复后看到本次消耗的 token 数，以便了解单次交互成本
2. 作为用户，我希望在每次回复后看到 session 累计 token 数，以便控制整体用量
3. 作为用户，我希望在输入 prompt 前看到剩余 token budget，以便决定是否继续对话

### 运行时安全

4. 作为用户，我希望配置 `provider: "local"` 时得到明确的错误提示，而不是运行时 `NotImplementedError` 崩溃
5. 作为开发者，我希望自定义错误类型不会遮蔽 Python 内置异常，以避免隐蔽的 bug
6. 作为开发者，我希望 Sandbox 的 I/O 操作不阻塞事件循环，以保持 agent 的响应性

### 功能正确性

7. 作为开发者，我希望 Memory 操作的 trace span 能正确记录到 trace 日志中，以便排查 memory 行为
8. 作为用户，我希望执行一条无输出的 shell 命令时不被标记为错误
9. 作为用户，我希望 `agent skill list` 能展示实际可用的技能，而不是永远显示 "(no skills loaded)"
10. 作为开发者，我希望恢复策略的 fallback 查找能找到实际的备用工具，而不是静默跳过
11. 作为开发者，我希望 `_glob` 搜索有结果数量限制，以避免返回数千条结果淹没上下文

### 代码质量

12. 作为开发者，我希望删除所有未使用的死代码，以降低代码库的认知负荷
13. 作为开发者，我希望 `SubagentTool` 只有一个实现，以避免选择错误的版本
14. 作为开发者，我希望所有 LLM 调用统一使用 `complete_with_tools`，以消除废弃警告
15. 作为开发者，我希望关键路径的异常至少有 warning 级别日志，而不是被静默吞掉
16. 作为开发者，我希望 runtime 不访问其他组件的私有属性，以保持封装性
17. 作为开发者，我希望 Sandbox 在使用前被正确初始化（`on_start()` 被调用）
18. 作为开发者，我希望 `QualityScorer` 如果仍在使用就不标记为废弃

### 文档与测试

19. 作为开发者，我希望文档中关于 `@tool_schema` 的建议与实际代码一致
20. 作为开发者，我希望测试有共享的 conftest.py 以减少 fixture 重复
21. 作为开发者，我希望有覆盖率配置以便衡量测试质量
22. 作为开发者，我希望不存在不验证任何东西的空壳测试

## Implementation Decisions

### Token 估算与显示

- `memory/__init__.py` 的 `__all__` 中删除不存在的 `TokenEstimator`。`estimate_tokens()` 函数已完整实现且被广泛使用，不需要额外包装类。
- 在 CLI chat 模式中增加三处 token 显示：
  - 每次回复后追加 `Tokens: ~N` 显示本次 token 消耗
  - 每次回复后追加 `Session total: ~N` 显示累计消耗
  - prompt 前缀中追加 `[budget: remaining/total]` 显示剩余预算
- Token 数据来源：`RuntimeMemory._total_tokens()` 用于当前用量，`MemoryConfig.runtime_token_budget` 用于总预算。

### Provider 清理

- 删除 `LocalProvider` 类及其在 `ProviderFactory` 中的注册。该 provider 的 `complete()` 返回硬编码字符串，且缺少 `complete_with_tools`，无法在 ReAct 循环中使用。

### 错误类型重命名

- `errors.py` 中 `MemoryError` 重命名为 `AgentMemoryError`。全局搜索并更新所有引用。
- 导入该类型的代码同步更新。

### Sandbox 异步修复

- `DaytonaSandbox`：`read_file()` 和 `write_file()` 中的同步 SDK 调用用 `asyncio.to_thread()` 包装。`exec()` 已有正确实现作为参考模式。
- `DockerSandbox`：`exec()`、`read_file()`、`write_file()` 中所有 `self._container.xxx()` 调用用 `asyncio.to_thread()` 包装。
- Sandbox 的 `on_start()` 在 runtime 的 `on_start()` 中显式调用，确保 `_workspace`/`_container` 在使用前初始化。

### SemanticKB 删除

- 删除 `memory/semantic.py` 整个文件。
- 删除 `memory/factory.py` 中的 `create_semantic_kb()` 方法。
- 删除 `memory/__init__.py` 中 `SemanticKB`、`InMemorySemanticKB` 的导入和 `__all__` 条目。
- `memory/__init__.py` 中 `create_semantic_kb` 的导出一并移除。

### Memory Tracing 修复

- Runtime 的 `on_start()` 中，在创建所有 memory 实例后，将 `self._trace_manager` 和当前 trace ID 注入到每个 memory 实例上：
  - `self._runtime_memory._trace_manager = self._trace_manager`
  - `self._profile_memory._trace_manager = self._trace_manager`
  - `self._retrieval_memory._trace_manager = self._trace_manager`
  - `self._archive_memory._trace_manager = self._trace_manager`
  - 同理设置 `_current_trace_id`。
- 每次 `run()` 开始时更新 `_current_trace_id`。

### `complete_structured` → `complete_with_tools` 迁移

- 将以下 8+ 处调用从 `complete_structured` 迁移到 `complete_with_tools`：
  - `routing/complexity.py`
  - `routing/domain.py`
  - `routing/unified.py`
  - `routing/intent.py`
  - `agent/react.py`（fallback 路径）
  - `agent/planner.py`
  - `eval/judge.py`
- 迁移后删除所有 provider 中的 `complete_structured` 方法及 `DeprecationWarning`。

### Skill CLI 接入

- `cli.py` 的 `skill` 命令中导入 `SkillRegistry`，调用 `scan_builtin_skills()` 加载技能，遍历注册表展示技能名称、描述、来源目录。

### SubagentTool 统一

- 删除 `subagent/tool.py` 整个文件。
- 从 `subagent/__init__.py` 中移除对 `SubagentTool` 的导入和导出。
- Runtime 继续使用 `tools/subagent.py` 中的版本（已在用，无需改导入）。

### OutputValidation 空输出修复

- `ExecTool.validate_output()`：区分"命令执行成功但无输出"和"命令执行失败"。空输出返回空列表（合法），非零退出码或异常返回错误。
- `ReadFileTool.validate_output()`：区分"文件为空"和"文件不存在/无法读取"。空文件返回空列表，读取失败返回错误。

### SQLite 并发与 assert 修复

- `RuntimeMemory` 添加 `threading.Lock`，在 `_persist_message` 的 `asyncio.to_thread` 调用中通过 lock 保护写入操作。
- `ProfileMemory` 中 `assert self._conn` 改为 `if not self._conn: raise RuntimeError(...)`。

### 私有属性访问修复

- 给 `RuntimeMemory` 添加 `get_recent_messages(n: int)` 公开方法，返回最近 n 条消息。
- 给 `CheckpointManager` 添加 `close_storage()` 公开方法。
- Runtime 中对应的 `._messages` 和 `._storage` 访问改为调用这些公开方法。

### 恢复策略无效路径清理

- 删除 `RetrievalRecoveryStrategy._expand_query()` 方法（只返回 `"query OR *"` 的 stub）。
- 删除 `ServiceRecoveryStrategy` 中通过 `"fallback"` tag 查找工具的逻辑（无工具注册该 tag）。
- 调用方直接移除这些路径，不保留 fallback 分支。

### SearchTool._glob 限制

- `_glob` 方法添加 `max_results=200` 参数，超出时截断并追加提示文本。

### 静默异常分级处理

- **关键路径**（config 解析、runtime 初始化）的 `except ... pass` 改为 `logger.warning(...)`。
- **非关键路径**（trace 持久化、memory span 创建）的 `except ... pass` 改为 `logger.debug(...)`。

### 死代码清理

全部删除以下未使用代码：

- `WorkingMemory` 类和 `create_working_memory()` 工厂方法
- `EpisodicStore` 类和 `create_episodic_store()` 工厂方法
- `UserProfileState` 类和 `create_user_profile()` 工厂方法
- `base.py` 中的 `ToolExecutor`、`IntentRecognizer`、`Router`、`LifecycleState`
- `agent/react.py` 中的 `Reflection` 数据类
- `agent/planner.py` 中 `Plan.current_step()` 和 `Plan.is_complete()` 方法
- `routing/router.py` 中的 `RoutingPipeline.evaluate()`、`get_routing_trace()`、`RoutingTraceData`
- `skills/matcher.py` 中的 `SkillMatcher.cleanup()`
- `monitoring/collector.py` 中未被调用的 `TraceCollector.collect_trace()` 和 `query_live_spans()`
- `provider/` 空目录
- `tools/todo.py` 中的 `TODO_TOOL_SCHEMA` 常量
- `cli.py` 中未使用的 `_ptk_prompt` import
- `runtime.py` 中 `_missing_slots_hint` 的硬编码中文改为英文

### `generate_clarification` 清理

- 删除 `runtime.py` 中对 `generate_clarification()` 的调用。当前 LLM 三分类路由不需要澄清步骤。

### QualityScorer 废弃标记移除

- 移除 `monitoring/collector.py` 中 `QualityScorer` 类的废弃 docstring。该类在 runtime 中有实际用途（实时打分），与 `eval.metrics`（事后评估）职责不同。

### 文档更新

- `docs/adding-tools.md` 中关于 `@tool_schema` 废弃的建议修改为：sandbox 场景下 `@tool_schema` 是推荐用法，Tool ABC 继承适用于独立工具类。

### 测试基础设施

- 创建 `tests/conftest.py`，提取以下共享 fixture：
  - `mock_provider`：返回预设响应的 mock provider
  - `tool_registry`：预注册了常用工具的 ToolRegistry
  - `routing_decision`：带默认值的 RoutingDecision
  - `safety_manager`：SafetyManager 实例
  - `permission_guard`：PermissionGuard 实例
- `pyproject.toml` 添加 `[tool.pytest.ini_options]` 中的覆盖率配置和标记注册（`slow`、`integration`、`unit`）。
- 删除 `test_runtime_memory_tool_messages.py` 中的空壳测试。

## Testing Decisions

### 测试策略

- **外部行为测试优先**：只测试公开 API 的行为，不测试内部实现细节。
- **最高测试接缝**：优先通过 `AgentRuntime.run()` 端到端测试，其次通过 `ToolRegistry.execute()` 测试工具行为，最后通过直接调用工具方法测试。

### 测试范围

| 修改区域 | 测试接缝 | 优先参考 |
|---------|---------|---------|
| Token 显示 | CLI chat 集成测试 | `test_cli_verbose_debug.py` |
| Provider 删除 | `test_provider_tools.py` | 已有 provider 测试 |
| Error 重命名 | `test_recovery.py` | 已有错误类型测试 |
| Sandbox 异步 | `test_docker_hardening.py` | 已有 sandbox 测试 |
| SemanticKB 删除 | 无需新测试（删除代码） | — |
| Memory tracing | `test_memory_spans.py` | 已有 span 测试 |
| complete_structured 迁移 | `test_unified_routing.py`, `test_agent.py` | 已有路由和 agent 测试 |
| Skill CLI | `test_skills.py` | 已有 skill 测试 |
| SubagentTool 统一 | `test_subagent.py` | 已有子 agent 测试 |
| OutputValidation | `test_middleware_chain.py` | 已有中间件测试 |
| SQLite 并发 | `test_checkpoint_sqlite_default.py` | 已有 SQLite 测试 |
| 死代码删除 | 现有测试不应受影响 | 运行全量 `pytest` 验证 |

### 回归保障

- 每个波次完成后运行 `make check`（`pytest tests/ -x -q` + lint）确认无回归。
- 死代码删除后特别注意：`from open_agent.memory import ...` 的外部导入是否报错。

## Out of Scope

- **不新增模块级单元测试** — 仅修复结构性测试问题（conftest.py、覆盖率配置、空壳测试），不补 9 个无测试模块的新测试
- **不实现真正的语义搜索** — 删除 stub，将来需要时基于 `RetrievalMemory` + `EmbeddingService` 扩展
- **不改路由层逻辑** — 路由的三分类（simple/moderate/complex）保持不变
- **不改 ReAct 循环核心逻辑** — ReAct loop 的 think-act-observe 机制保持不变
- **不引入新依赖** — 所有修复使用已有依赖（`asyncio.to_thread`、`threading.Lock` 等）
- **不做 i18n 框架** — 仅将硬编码中文改为英文，不建立多语言体系
- **不迁移 sandbox 的 `@tool_schema` 到 Tool ABC** — sandbox 的动态 schema 注册方式保留

## Further Notes

### 执行顺序

建议按 P0 → P1 → P2 顺序执行，因为：
- P0 修复崩溃风险，为后续改动提供安全基础
- P1 是主体改动，其中死代码清理应放在最后（减少合并冲突）
- P2 收尾，在代码稳定后补测试基础设施

### 风险点

- `complete_structured` → `complete_with_tools` 迁移影响面最广（8+ 文件），需要仔细验证每个调用点的参数映射和返回值解析是否兼容。
- 死代码删除后需要全量 `pytest` 验证，特别是向后兼容导出的删除可能影响外部消费者。
- `MemoryError` 重命名需要全局搜索替换，包括测试文件中的引用。

### 总改动量估算

- 删除代码：~800 行（死代码、重复实现、无效路径）
- 修改代码：~300 行（Sandbox 异步、tracing 注入、异常日志、空输出修复等）
- 新增代码：~100 行（公开方法、conftest.py、token 显示）
- 净减少：~400 行
