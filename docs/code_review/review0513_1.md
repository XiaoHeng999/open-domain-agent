# Open Agent 项目代码审查报告（第二轮 — 功能完整性 & 集成审计）

> **审查日期**：2026-05-13
> **审查范围**：`src/open_agent/` 全部 96 个 Python 源文件 + `openspec/specs/` 46 个规范文件
> **审查维度**：未完成功能、死代码、实现错误、集成断点
> **审查方法**：规范-实现交叉比对、调用链追踪、注册/注入完整性验证

---

## 一、已定义但未实现的功能（8 项）

### 1. `MCPClientTool` — 运行时 MCP 服务器动态管理工具

- **文件**: `tools/mcp_client.py`
- **设计**: 提供 `connect` / `disconnect` / `list` 三个操作，允许 Agent 在对话中动态连接/断开 MCP 服务器
- **现状**: 类已完整实现，但 `scan_builtin_tools()`（`registry.py:150-200`）和 `runtime.py` 均未实例化或注册此工具
- **影响**: `MCPServerManager` 仅在启动时引导预配置的服务器，Agent 无法在运行时动态管理 MCP 连接

### 2. `SandboxControlTool` — 沙箱生命周期控制工具

- **文件**: `tools/sandbox_control.py`
- **设计**: 提供 `start` / `exec` / `snapshot` / `restore` 四个操作，通过依赖注入获取 sandbox 后端
- **现状**: 全项目中没有任何代码实例化或注册此工具。沙箱后端仅通过 `_inject_sandbox_to_exec_tool()` 注入到 `ExecTool`
- **影响**: Agent 无法通过工具调用主动控制沙箱生命周期（创建快照、恢复等）

### 3. `SelfTool` — Agent 自我状态检查工具

- **文件**: `tools/self.py`
- **设计**: 提供 `status` / `get_config` / `set_config` 操作，通过 weakref 引用 ReActLoop 和 Runtime
- **现状**: 全项目中没有实例化或注册此工具
- **影响**: Agent 无法通过工具调用查看或修改自身运行时状态（如迭代次数上限、staleness 回合数等）

### 4. `wechat-mp-cn` 技能包 — 规划但从未创建

- **规范**: `openspec/specs/skill-extensions/` 明确列出 `wechat-mp-cn` 为内置技能包
- **现状**: `skills/builtin/` 目录下不存在 `wechat-mp-cn/` 目录

### 5. 技能 Python Handler 注册机制 — 未实现

- **规范**: `skill-extensions` 规范要求每个技能目录包含 `.py` handler 文件，导出 `register(registry)` 方法
- **现状**: 所有 builtin 技能（`weather`、`github`、`summarize`、`skill-creator`）都仅有 `SKILL.md`，无 Python handler
- **影响**: 技能系统仅支持指令注入型技能，无法通过技能注册新工具

### 6. CLI `eval` 命令 — 仅占位符

- **文件**: `cli.py:147-162`
- **现状**: 硬编码输出 `"(no scenarios yet)"` 行，未调用 `eval/` 子系统中的 `EvalDataset`、`TraceReplayEngine`、`LLMJudge` 等任何组件

### 7. CLI `skill list` 命令 — 仅占位符

- **文件**: `cli.py:214-227`
- **现状**: 硬编码输出 `"(no skills loaded)"` 行，未调用 `SkillRegistry.scan_builtin_skills()` 或 `scan_workspace_skills()`

### 8. `TraceConfig` — 配置定义但从未被消费

- **文件**: `config.py:125-131`
- **字段**: `enabled` / `store_traces` / `trace_dir`
- **现状**: 运行时和 trace 系统从未读取这些配置。Trace 系统始终启用，CLI 的 `trace` 命令使用硬编码路径 `.open_agent/traces`

---

## 二、已实现但未使用的功能（死代码，8 项）

### 1. `fallback.py` — `FallbackChain` 类

- **文件**: `fallback.py`（86 行）
- **现状**: 无任何生产代码导入或使用。仅在 `tests/test_harness.py` 中有测试用例
- **建议**: 移除或标记为未来计划

### 2. `provider/` 包 — 空目录

- **文件**: `provider/__init__.py`（0 字节）
- **现状**: 全项目无任何代码 `from open_agent.provider import ...`
- **建议**: 删除空包

### 3. `memory/episodic.py` — `EpisodicStore`（旧版兼容）

- **文件**: `memory/episodic.py`（147 行）
- **现状**: 除 `memory/__init__.py` 的 re-export 外零导入。已被 `RetrievalMemory` 的 Episodic 子层取代

### 4. `memory/semantic.py` — `InMemorySemanticKB`（旧版兼容）

- **文件**: `memory/semantic.py`（57 行）
- **现状**: 除 `memory/__init__.py` 的 re-export 外零导入。已被 `RetrievalMemory` 的 Semantic 子层取代

### 5. `memory/working.py` — `WorkingMemory`（旧版兼容）

- **文件**: `memory/working.py`（145 行）
- **现状**: 仅在 2 个测试文件中导入，无生产代码使用。已被 `RuntimeMemory` 取代

### 6. `subagent/tool.py` — `SubagentTool` 的重复副本

- **文件**: `subagent/tool.py`（112 行）
- **现状**: `tools/subagent.py`（带 Rich 输出版）是被 `runtime.py` 实际使用的版本。`subagent/tool.py` 是更早的干净版本，功能几乎相同
- **影响**: 维护时需要同步两处代码，增加出错风险

### 7. `middleware.py:default_chain()` 的无效参数

- **文件**: `middleware.py:218-229`
- **现状**: `default_chain()` 接受 `safety_manager` / `permission_guard` / `max_tool_result_tokens` 参数但从未传递给任何中间件实例（值通过 `MiddlewareContext` 流转）
- **影响**: 误导性签名，调用者可能误以为参数生效

### 8. `ToolsConfig.max_tool_result_tokens` — 未使用的配置字段

- **文件**: `config.py:133-139`
- **现状**: 运行时读取的是 `config.memory.max_tool_result_tokens`，`config.tools` 上的同名字段从未被访问

---

## 三、实现错误（7 项，3 HIGH + 4 MEDIUM）

### HIGH — 必须立即修复

#### H1. SSRF 防护完全失效 — DNS 解析从未执行

- **文件**: `safety/ssrf.py:92-99`
- **代码**:
  ```python
  def _check_hostname_ip(self, hostname: str) -> SafetyCheckResult:
      try:
          addr = ipaddress.ip_address(hostname)
          return self.check_ip(str(addr))
      except ValueError:
          pass  # Not a literal IP, OK for now (DNS resolution check deferred)
      return SafetyCheckResult(safe=True, risk_level="safe")
  ```
- **问题**: 当 hostname 不是字面 IP（如 `evil.attacker.com`）时直接返回 `safe=True`。`check_resolved_ip` 方法存在（第 101-110 行）但从未被调用
- **影响**: 攻击者可通过域名指向私有 IP（`127.0.0.1`、`169.254.169.254`）绕过全部 SSRF 检查
- **修复**: 在 `check_url()` 中对非字面 IP 的 hostname 执行 DNS 解析后调用 `check_resolved_ip()`

#### H2. SSRF — IPv4-mapped IPv6 地址绕过

- **文件**: `safety/ssrf.py:14-22, 75-90`
- **问题**: `::ffff:127.0.0.1` 等 IPv4-mapped IPv6 地址能绕过检查。`ipaddress.ip_address()` 解析后得到 `IPv6Address` 对象，但 `_PRIVATE_NETWORKS` 中的 `127.0.0.0/8` 等 IPv4 网络无法匹配 IPv6 对象
- **影响**: 攻击者使用 IPv4-mapped IPv6 表示法即可访问私有网络资源
- **修复**: 在 `check_ip()` 中对 IPv4-mapped IPv6 地址先提取内嵌 IPv4 再检查

#### H3. MCP STDIO 传输无并发保护

- **文件**: `mcp_integration.py:162-173`
- **代码**:
  ```python
  async def _call_stdio(self, tool_name: str, arguments: dict[str, Any]) -> Any:
      request_id, payload = self._build_request("tools/call", {"name": tool_name, "arguments": arguments})
      self._process.stdin.write((payload + "\n").encode())
      await self._process.stdin.drain()
      response_line = await asyncio.wait_for(self._process.stdout.readline(), timeout=30)
      raw = json.loads(response_line)
      return self._parse_response(raw, request_id)
  ```
- **问题**: 对共享子进程的 stdin/stdout 读写无 `asyncio.Lock`。并发调用会交叉写入和错误读取响应。规范要求的 `pending_requests` 字典也未实现
- **影响**: 多个并发工具调用将导致请求/响应错位，返回错误数据
- **修复**: 添加 `asyncio.Lock` + `pending_requests` 字典匹配 request_id

---

### MEDIUM — 应尽快修复

#### M1. Memory → Prompt 数据断裂

- **文件**: `runtime.py:382-417` 与 `react.py:693-748`
- **问题**: `runtime.py` 组装了 `prompt_context` 字典包含 `user_profile`（用户画像）、`retrieval_results`（检索结果）、`plan`（执行计划），但该 dict 从未传递给 `PromptBuilder` 或 `ReActLoop.run()`。ReActLoop 的 `_build_messages()` 自行构建了只含 `matched_skills`/`todo_plan`/`missing_slots_hint` 的独立 context
- **影响**:
  - `ProfileMemory` 的用户偏好/约束/技术栈永远无法注入系统提示
  - `RetrievalMemory` 的语义/情景检索结果永远无法被 Agent 感知
  - `PlanGenerator` 的执行计划永远无法指导 ReAct 循环
- **修复**: 将 `runtime.py` 的 `prompt_context` 传递给 `self.react_loop.run()`，并在 `ReActLoop._build_messages()` 中合并

#### M2. Final-answer guard 不完整

- **文件**: `react.py:373-378, 766-809`
- **问题**: 没有 LLM 验证最终答案是否与用户问题相关。`_compose_final_answer` 直接返回工具输出或错误摘要
- **影响**: 工具返回嘈杂输出时，用户会收到无意义的回复
- **修复**: 添加 LLM-based 相关性验证，或至少检查最终答案非空且非纯工具输出

#### M3. `on_stop()` 资源泄漏

- **文件**: `runtime.py:320-332`
- **问题**:
  - 未调用 `self.provider.on_stop()`（provider 的 HTTP 客户端连接池泄漏）
  - 未关闭 `_runtime_memory`、`_retrieval_memory`、`_archive_memory`（文件句柄/数据库连接可能泄漏）
- **修复**: 在 `on_stop()` 中补充所有子系统的清理逻辑

#### M4. 多工具顺序执行而非并行

- **文件**: `react.py:282`
- **代码**: `for act in actions: obs = await self._execute_action(act, ...)`
- **问题**: 规范要求并行处理所有 `tool_use` blocks，但实现是 `for` 循环顺序执行
- **影响**: 当 LLM 返回多个独立工具调用时，总延迟是各工具执行时间之和而非最大值
- **修复**: 改用 `asyncio.gather()` 并行执行独立的工具调用

---

## 四、集成完整性矩阵

| 集成点 | 状态 | 说明 |
|--------|------|------|
| SubagentManager → Runtime | **WORKING** | 初始化、注册、启动、停止全链路正常 |
| Memory → Prompt | **PARTIAL** | Profile/Retrieval/Plan 数据组装后未传递到 PromptBuilder |
| Routing → ReAct | **WORKING** | Domain prompt、skip_planning、missing_slots 均正常流转 |
| Hook 系统 | **WORKING** | SESSION_START / TOOL_BEFORE / TOOL_AFTER 均在正确位置触发 |
| Recovery 集成 | **WORKING** | RecoveryChain 在 ToolError 时被调用，成功/失败路径均已处理 |
| MCP 集成 | **PARTIAL** | MCPServerManager 启动配置正常；MCPClientTool 未注册（死代码） |
| SandboxControlTool 注入 | **BROKEN** | 类存在但从未实例化或注册 |
| SelfTool 注入 | **BROKEN** | 类存在但从未实例化或注册 |
| PromptBuilder → ReAct | **WORKING** | PromptBuilder 正确用于 _build_messages，有 fallback 路径 |
| CheckpointManager → ReAct | **WORKING** | 每步保存、恢复/续跑均正常 |

---

## 五、优先修复建议

### 立即修复（P0）

1. **SSRF 防护修复** — 在 `check_url()` 中对非字面 IP hostname 执行 DNS 解析 + 处理 IPv4-mapped IPv6 + 非标准 IP 表示
2. **MCP STDIO 并发保护** — 添加 `asyncio.Lock` + `pending_requests` 字典
3. **Memory → Prompt 数据断裂修复** — 将 `runtime.py` 的 `prompt_context` 传递到 ReActLoop

### 尽快修复（P1）

4. **注册三个未接入的工具** — 在 `runtime.py` 的 `on_start()` 中实例化并注册 `SelfTool`、`SandboxControlTool`、`MCPClientTool`
5. **资源泄漏修复** — 在 `on_stop()` 中补充 provider、runtime_memory、retrieval_memory、archive_memory 的清理
6. **并行工具执行** — 改用 `asyncio.gather()` 处理多个独立 tool_use blocks

### 代码清理（P2）

7. **删除死代码** — `fallback.py`、`provider/` 包、`subagent/tool.py` 重复副本
8. **清理旧版兼容模块** — `memory/working.py`、`memory/episodic.py`、`memory/semantic.py`
9. **完善 CLI 占位命令** — 实现 `eval` 和 `skill list` 的实际逻辑
10. **清理无效配置** — `TraceConfig` 全部字段、`ToolsConfig.max_tool_result_tokens`、`middleware.py:default_chain()` 的无效参数
