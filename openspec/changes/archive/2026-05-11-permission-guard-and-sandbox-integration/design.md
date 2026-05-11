## Context

open_agent 当前有完整的安全检查层（SafetyManager: command blacklist, SSRF, path traversal）和独立的 sandbox 模块（subprocess/docker/daytona 三后端），但存在三个断点：

1. **SafetyManager 只做检查不做决策** — 告诉你命令危不危险，但不告诉你能不能执行。`safety_level` 只有 strict/permissive/off 三档，permissive 下所有写操作自动放行。
2. **HITLApprovalManager 实现了但从未被调用** — 三层审批（Read/Write/Dangerous）代码完整，但在 `ToolRegistry.execute()` 和 ReAct 循环中无任何调用点。
3. **Sandbox 实例创建但未使用** — `AgentRuntime` 创建 sandbox 并在 `on_stop()` 中关闭，但 `ExecTool` 直接用 `asyncio.create_subprocess_shell` 在宿主机执行。

当前执行路径：`ReActLoop._execute_action() → ToolRegistry.execute() → safety_checks → tool.execute()`。所有改动需在此路径内收敛。

## Goals / Non-Goals

**Goals:**
- 在 `ToolRegistry.execute()` 中插入权限决策层，实现 deny → mode → allow → ask 四级管线
- 复用现有 `HITLApprovalManager` 作为 ask user 级别的执行者
- 让 `ExecTool` 支持依赖注入 sandbox，实现隔离执行
- ReAct 循环零修改，所有改动收敛在 ToolRegistry 和 Tool 实例层
- 配置通过 YAML + Pydantic，规则用 glob 匹配（`fnmatch`，无新依赖）

**Non-Goals:**
- 不实现 auto mode（Claude Code 用小模型分类器，成本高且依赖外部推理）
- 不实现 acceptEdits 模式（Claude Code 特有的前端编辑场景，不适用于框架层）
- 不改动 sandbox 后端本身的实现（docker/daytona/subprocess 保持原样）
- 不实现 managed settings 或 MDM 级别的组织策略（这是框架，不是 SaaS 产品）
- 不实现网络级 egress 过滤（SSRF 检查在 URL 层已足够，不做网络代理）

## Decisions

### Decision 1: PermissionGuard 作为独立中间件 vs 扩展 SafetyManager

**选择**：独立 `PermissionGuard` 类，放在 `safety/permission.py`。

**理由**：SafetyManager 职责是"检查安全性"（这个 URL 危不危险），PermissionGuard 职责是"做权限决策"（这个操作允不允许）。关注点不同。独立出来后，SafetyManager 可以在权限检查之前运行（先检查安全性，再决定权限），顺序合理。如果合并到 SafetyManager 中，类会变得过大且职责不清。

**备选**：扩展 SafetyManager 加 `check_permission()` 方法。问题：SafetyManager 已经有 4 个子模块（command/ssrf/workspace/hitl），再加权限决策会让它变成 God Object。

### Decision 2: 规则格式 — YAML 结构化 vs Claude Code 的 Tool(pattern) 字符串

**选择**：YAML 结构化规则，每条规则是一个对象 `{tool, pattern?, path?, domain?}`。

**理由**：框架配置走 YAML，不是 CLI 参数。结构化格式更易序列化、校验（Pydantic）和 IDE 补全。Claude Code 的 `Bash(npm run *)` 格式适合终端但不好在 YAML 里表达嵌套逻辑。

**备选**：用字符串格式 `exec(git status)` 然后解析。问题：需要额外解析器，且 YAML 本身就是结构化格式，没必要降级为字符串协议。

### Decision 3: 4 种权限模式而非 6 种

**选择**：cautious / conservative / fluent / unrestricted 四种。

**理由**：
- `cautious`：Claude Code 的 `default` 模式等价 — 除了 read-only 都问用户
- `conservative`：新增 — 只允许读，写操作直接拒绝。适用于审查/审计场景
- `fluent`：Claude Code 的 `acceptEdits` 概念延伸 — read-only + allow 规则自动放行，其余问用户
- `unrestricted`：Claude Code 的 `bypassPermissions` — 只有 deny 规则生效

不采用 auto（需要小模型分类器）、plan（read-only 已被 conservative 覆盖）、dontAsk（可由 unrestricted + deny 规则组合实现）。

### Decision 4: Sandbox 注入方式 — ExecTool 构造函数注入 vs 全局 registry 层路由

**选择**：ExecTool 构造函数注入可选 sandbox 实例。

**理由**：只有 `exec` 工具需要 sandbox（其他工具如文件操作走 SafetyManager path check）。通过构造函数注入，ExecTool 内部决定走 sandbox 还是宿主机，不需要改动 registry 或 ReAct 循环。如果后续其他工具也需要 sandbox，可以在 Tool ABC 层加 `needs_sandbox` 属性，但当前不需要。

**备选**：在 ToolRegistry 层判断工具是否需要 sandbox 并路由。问题：Registry 不应该知道 sandbox 的存在，它只负责工具生命周期和执行管道。

### Decision 5: 接入点位置 — safety_checks 之后

**选择**：在 `ToolRegistry.execute()` 的 `_run_safety_checks()` 之后、`tool.execute()` 之前插入权限检查。

**理由**：顺序是 安全性 → 权限 → 执行。先检查操作是否安全（命令有没有危险），再检查是否有权限执行（当前模式允不允许），最后执行。这个顺序合理：一个安全的操作可能因为权限模式被拒绝（conservative 下写文件），一个有权限的操作可能因为不安全被阻止（rm -rf）。

## Risks / Trade-offs

**[性能] PermissionGuard 每次工具调用增加一次规则匹配** → 规则列表通常 < 50 条，`fnmatch` 匹配是微秒级，可忽略。如果规则列表增长到数百条，可以加 tool name 索引优化。

**[兼容性] 新增 `permissions` 配置段，旧配置无此段** → Pydantic `Field(default_factory=...)` 确保缺失时使用默认值（mode=fluent, 空 deny/allow 列表），旧配置文件无需修改。

**[HITL] ask user 级别在非交互环境（CI/API）下会阻塞** → `HITLApprovalManager` 已有 `interactive=False` 参数。PermissionGuard 在初始化时从配置读取是否交互模式。非交互模式下 ask 级别默认拒绝。

**[Sandbox] Docker sandbox 需要额外基础设施** → 默认 `backend=subprocess`（零隔离但零依赖），用户显式配置 `docker` 或 `daytona` 才启用隔离。SubprocessSandbox 保持向后兼容。

**[解耦] PermissionGuard 不感知 sandbox** → 权限层决定"能不能执行"，sandbox 层决定"怎么执行"。两层互不依赖，可以独立使用。后续如果需要"在 sandbox 中执行的不需要问权限"，可以在 PermissionGuard 的 allow 规则中配置。
