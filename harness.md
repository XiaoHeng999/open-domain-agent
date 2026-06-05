# 双层 Harness Engineering 分析与规划

> 基于 [Learn Harness Engineering](https://walkinglabs.github.io/learn-harness-engineering/zh/) 课程体系，对 open_agent 项目的 Harness Engineering 差距分析与实现规划。

## 0. 总体评估

代码库在**基础设施层**做得相当扎实——ReAct 循环、中间件管道、安全系统、检查点、4 层记忆、路由、沙箱、子 agent 等核心机制都已实现。但从 Harness Engineering 的视角看，这些是"让 agent 能跑起来的机制"，课程强调的是**"让 agent 可靠地完成任务的工作系统"**。两者之间存在一个关键视角差异：

| 维度 | 当前代码库（侧重） | Harness Engineering（课程侧重） |
|------|-------------------|-------------------------------|
| 关注点 | agent 的执行能力 | agent 的任务完成可靠性 |
| 核心机制 | 工具/安全/恢复等内部机制 | 指令/环境/状态/验证/反馈等外部约束 |
| 状态管理 | 执行级状态（checkpoint） | 项目级状态（progress/feature list） |
| 验证方式 | 后置质量评分（QualityScorer） | 前置验证门控（pass-through gating） |
| 可观测性 | 运行时 traces/spans | 双层可观测（runtime + process） |
| 终止判定 | 确定性停止条件 | 三层终止检查 |

### 当前已完成的能力

| 机制 | 实现质量 | 对应课程概念 |
|---|---|---|
| ReAct 循环 + 确定性停止 | ★★★★ | 执行引擎 |
| 中间件管道 (5 层) | ★★★★★ | 工具执行控制 |
| 安全系统 (6 层防护) | ★★★★★ | 安全边界 |
| 检查点保存/恢复 | ★★★★ | 执行级状态持久化 |
| 错误恢复 (4 策略) | ★★★★ | 错误容忍 |
| 4 层记忆架构 | ★★★★ | 上下文管理 |
| 路由管道 (3 级) | ★★★★ | 任务分级 |
| 沙箱隔离 (3 后端) | ★★★★ | 执行隔离 |
| OTel 追踪 | ★★★ | 运行时可观测性 |
| Hook 系统 | ★★★ | 生命周期控制 |
| 子 agent 系统 | ★★★ | 任务委派 |
| 评估框架 | ★★★ | 质量评估 |

---

## 第一部分：Claude Code 开发 Harness

> 让 Claude Code（或任何 AI 编程助手）可靠地开发这个项目的环境。

### 现状诊断

| 课程要求的 5 个子系统 | 当前状态 | 评分 |
|---|---|---|
| 指令子系统（CLAUDE.md） | **完全缺失** — 没有 CLAUDE.md | 0/5 |
| 工具子系统 | 有 pytest、pyproject.toml，但没有 Makefile | 3/5 |
| 环境子系统 | pyproject.toml 存在，但缺 .python-version、无 init.sh | 2/5 |
| 状态子系统 | **完全缺失** — 没有 PROGRESS.md、feature_list.json | 0/5 |
| 反馈子系统 | 有 819 个测试，但没有 Makefile 整合验证命令 | 2/5 |

### 需要创建的文件

#### P0：CLAUDE.md — 指令路由文件

```
文件：/mnt/data_202/zjh/claude-demo/open_agent/CLAUDE.md

内容结构（≤200 行，作为路由器）：
├── 项目概述
│   └── open-agent 是基于 Harness Engineering 原则的开源 coding agent 框架
├── 技术栈
│   ├── Python 3.11+, Pydantic v2, Typer CLI, Rich
│   ├── 异步优先（async/await），所有 IO 操作都是 async
│   └── 可选依赖：OpenAI/Anthropic/DeepSeek SDK, Docker, Daytona
├── 快速开始命令
│   ├── 安装：uv pip install -e ".[dev,openai,anthropic]"
│   ├── 测试：make test 或 pytest tests/ -x
│   └── 运行：agent run "你的任务"
├── 硬约束（≤15 条）
│   ├── 所有新工具必须继承 Tool ABC（tools/base.py）
│   ├── 所有新组件必须有 on_start/on_stop 生命周期
│   ├── 安全检查不可绕过（SafetyMiddleware 必须在 ExecuteMiddleware 之前）
│   ├── 测试必须通过才能 commit
│   ├── 不要在 abc 方法中引入 breaking change
│   ├── 异步优先——新 IO 操作必须用 async
│   ├── 错误类型必须继承 errors.py 中的层级
│   ├── 配置项必须加入 config.py 的 Pydantic model
│   ├── 中间件链顺序：Safety → Permission → Execute → Validate → Truncate
│   └── 所有 public API 必须有 type hints
├── 架构文档链接（路由到详细文档）
│   ├── docs/architecture.md — 整体架构图
│   ├── docs/adding-tools.md — 如何添加新工具
│   ├── docs/adding-recovery.md — 如何添加恢复策略
│   └── docs/testing-guide.md — 测试规范
├── 会话启动流程
│   ├── 1. 读取 PROGRESS.md 了解当前状态
│   ├── 2. 运行 pytest tests/ -x 确认基线
│   └── 3. 从 PROGRESS.md 的"下一步"继续
└── 会话结束流程
    ├── 1. 运行 make check 确认一切通过
    ├── 2. 更新 PROGRESS.md
    ├── 3. 更新 feature_list.json（如有特性变更）
    └── 4. 确保干净的 git 状态
```

#### P0：Makefile — 验证命令整合

```makefile
文件：/mnt/data_202/zjh/claude-demo/open_agent/Makefile

.PHONY: test lint check install

install:
    uv pip install -e ".[dev,openai,anthropic]"

test:
    pytest tests/ -x -q

lint:
    ruff check src/open_agent/

typecheck:
    mypy src/open_agent/ --ignore-missing-imports

check: test lint typecheck
    @echo "All checks passed"
```

课程核心观点：`make check` 是 agent 最常用的命令，应该是**一条命令跑通所有验证**。

#### P0：PROGRESS.md — 项目进度跟踪

```
文件：/mnt/data_202/zjh/claude-demo/open_agent/PROGRESS.md

结构：
├── 当前验证状态
│   └── 最近一次 make check 的结果和时间
├── 仓库根目录
│   └── /mnt/data_202/zjh/claude-demo/open_agent
├── 标准启动路径
│   └── 读取 CLAUDE.md → 安装依赖 → 运行测试
├── 标准验证路径
│   └── make check
├── 当前最高优先级的未完成特性
│   └── （从 feature_list.json 同步）
├── 当前阻塞项
│   └── （如有）
└── 会话记录（按时间倒序）
    ├── 会话 N: 日期
    │   ├── 目标：xxx
    │   ├── 完成：xxx
    │   ├── 验证：pytest 结果
    │   ├── 证据：xxx
    │   ├── 提交：git commit hash
    │   ├── 已知风险：xxx
    │   └── 下一步最优行动：xxx
    └── 会话 N-1: ...
```

#### P0：feature_list.json — 特性列表

```
文件：/mnt/data_202/zjh/claude-demo/open_agent/feature_list.json

每个特性的三元组结构：
{
  "features": [
    {
      "id": "F001",
      "priority": "P0",
      "area": "verification",
      "title": "验证注册表和门控",
      "user_visible_behavior": "Agent 执行代码变更后自动运行关联的验证命令",
      "status": "not_started",
      "verification": ["pytest tests/test_verification.py -x"],
      "evidence": null,
      "notes": "课程 P0 优先级"
    }
  ]
}

规则：
- 同时只能有一个 status = "active"（WIP=1）
- "active" → "passing" 的唯一路径：verification 全部通过
- 状态转换不可逆（passing 不会回退）
```

#### P0：.claude/settings.json — Claude Code 配置

```
文件：/mnt/data_202/zjh/claude-demo/open_agent/.claude/settings.json

包含：
├── 允许的命令（减少权限提示）
│   ├── pytest, python -m pytest
│   ├── make test, make check, make lint
│   ├── uv pip install
│   ├── git status, git diff, git log
│   └── ruff check
├── 权限策略
│   └── 读取：自动允许；写入/执行：按规则
└── Hook 配置
    ├── PreToolUse: 阻止危险操作
    └── PostToolUse: 审计日志
```

#### P1：.python-version — 环境自描述

```
文件：/mnt/data_202/zjh/claude-demo/open_agent/.python-version
内容：3.11
```

#### P1：docs/ 下的主题文档

```
需要创建：
├── docs/architecture.md — 整体架构、组件关系图、数据流
├── docs/adding-tools.md — 如何添加新工具（Tool ABC 继承指南）
├── docs/adding-recovery.md — 如何添加恢复策略
├── docs/adding-middleware.md — 中间件开发指南
├── docs/testing-guide.md — 测试规范和约定
└── docs/harness-design.md — Harness Engineering 设计决策
```

#### P2：init.sh — 一键初始化脚本

```bash
#!/bin/bash
# init.sh — 一键环境初始化
set -e
INSTALL_CMD="uv pip install -e '.[dev,openai,anthropic]'"
VERIFY_CMD="pytest tests/ -x -q"
START_CMD="agent run 'Hello, open_agent!'"

echo "Installing dependencies..."
eval $INSTALL_CMD

echo "Running verification..."
eval $VERIFY_CMD

echo "Quick start command:"
echo "  $START_CMD"
```

#### P2：clean-state-checklist.md — 干净状态检查清单

```
会话结束前的 5 条件检查：
□ make check 通过（构建 + 测试 + lint）
□ PROGRESS.md 已更新
□ feature_list.json 准确反映 passing vs 未验证边界
□ 没有未记录的半成品（git status clean 或变更已解释）
□ 下一个会话的启动路径可用
```

### 第一部分优先级排序

| 优先级 | 文件 | 理由 |
|---|---|---|
| **P0** | CLAUDE.md | 课程核心：没有指令文件 = agent 没有工作指南 |
| **P0** | Makefile | 一条命令验证：`make check` |
| **P0** | PROGRESS.md | 跨会话连续性的唯一保障 |
| **P0** | feature_list.json | 特性级追踪 + WIP=1 + 验证门控 |
| **P0** | .claude/settings.json | 减少 Claude Code 权限提示，提升开发效率 |
| P1 | .python-version | 环境自描述 |
| P1 | docs/* 主题文档 | 指令路由架构的 topic docs |
| P2 | init.sh | 一键初始化 |
| P2 | clean-state-checklist.md | 会话结束检查 |

---

## 第二部分：Coding Agent 产品 Harness

> 让 agent 框架本身具备完整 harness 能力，可靠地完成任务。

### 差距 1：反馈/验证子系统（最高 ROI，当前最弱）

**课程核心观点**：反馈子系统是五个子系统中 ROI 最高的。Agent 必须有明确的验证命令，且验证必须通过才能宣告完成。

**当前状态**：
- `QualityScorer` 是后置评分机制（任务完成后打分），不是前置门控
- `OutputValidationMiddleware` 只验证工具输出的 JSON Schema，不验证代码质量
- 没有验证命令的定义和执行机制（没有 pytest、ruff check 等集成）
- 没有执行架构约束的能力

**需要新增**：

```
新增模块：src/open_agent/verification/

├── __init__.py
├── registry.py          # VerificationRegistry
│   ├── 注册验证命令
│   ├── 关联文件模式 → 验证命令（*.py → pytest, *.ts → tsc + jest）
│   ├── 预定义模板（pytest, ruff, mypy, eslint, tsc, make, cargo test）
│   └── 用户自定义验证命令（从 config.yaml 加载）
│
├── runner.py            # VerificationRunner
│   ├── async run_single(command) → VerificationResult
│   ├── async run_layer(layer) → LayerResult
│   ├── 结果解析：通用 exit code + 特定解析器
│   ├── 超时控制（可配置，默认 60s）
│   └── 增量验证：只运行受影响文件相关的验证
│
├── parsers.py           # 结果解析器
│   ├── PytestParser     # 解析 pytest 输出 → structured failures
│   ├── RuffParser       # 解析 ruff 输出 → lint violations
│   ├── MypyParser       # 解析 mypy 输出 → type errors
│   ├── GenericParser    # 通用 exit code + stderr
│   └── AgentOrientedFormatter  # 格式化为面向 agent 的错误信息
│       # 包含：出什么问题 + 为什么 + 怎么修
│
├── gate.py              # VerificationGate
│   ├── pre_completion_check(task_id) → bool
│   │   # 任务标记完成前的强制验证
│   │   # 验证不通过 → 注入错误到 agent 上下文 → agent 必须继续
│   ├── file_change_trigger(changed_files) → List[VerificationCommand]
│   │   # 文件变更后自动触发关联验证
│   └── incrementality(file_patterns) → optimized_command_set
│
└── termination.py       # TerminationChecker（三层终止检查）
    ├── Layer 1: StaticAnalysisLayer
    │   └── lint + type check（低成本、低信息、必须通过）
    ├── Layer 2: RuntimeBehaviorLayer
    │   └── 单元测试 + 应用启动 + 关键路径验证（核心完成证据）
    ├── Layer 3: SystemConfirmLayer
    │   └── E2E 测试 + 集成验证 + 用户场景模拟（最终防线）
    ├── check_all() → TerminationResult
    │   └── 逐层执行，某层失败则停止，返回修复指引
    └── RefactoringGuard
        └── 核心功能验证通过前禁止重构操作
```

**集成点**：
- `ReActLoop._think_and_act()` → agent 返回直接回答时，触发 `TerminationChecker`
- `TodoTool.complete_task()` → 标记完成前必须通过 `VerificationGate`
- `WriteFileTool/EditFileTool` → 执行后触发关联验证
- `SafetyMiddleware` → "重构守卫"作为安全检查的一环

**配置模型**：

```python
class VerificationConfig(BaseModel):
    enabled: bool = True
    layers: List[VerificationLayer] = []
    pre_completion_gate: bool = True
    refactoring_guard: bool = True
    auto_trigger_on_file_change: bool = True
    default_timeout: int = 60
```

**严重程度**：**P0 - 关键缺失**。课程明确指出"没有验证的完成是虚假的完成"。

---

### 差距 2：状态子系统（项目级状态 vs 执行级状态）

**课程核心观点**：长任务需要 PROGRESS.md 跟踪进度，遵循 ACID 原则，每次会话结束前必须更新，每次会话开始时必须读取。

**当前状态**：
- 检查点系统只保存执行级状态（tool_messages、step_number），不保存项目级状态
- 没有 PROGRESS.md 或等效机制
- TodoTool 是会话级的，不会跨会话持久化到项目文件
- 没有 ACID 语义

**需要新增**：

```
新增模块：src/open_agent/state/

├── __init__.py
├── progress.py          # ProgressTracker
│   ├── auto_generate_progress_md()
│   │   # 从 feature_list + todo + git status 自动生成 PROGRESS.md
│   ├── update_on_step(step_summary)
│   ├── update_on_session_end(session_summary)
│   ├── read_on_session_start() → ProgressSnapshot
│   └── ProgressSnapshot 结构：
│       ├── verified_state: 当前验证状态
│       ├── highest_priority_incomplete: 最高优先级未完成特性
│       ├── blockers: 当前阻塞项
│       └── next_best_action: 下一步最优行动
│
├── feature_list.py      # FeatureListManager
│   ├── load(path) / save(path)
│   ├── 三元组：(behavior, verification_commands, state)
│   ├── 状态机：not_started → active → passing（不可逆）
│   │   ├── activate(feature_id)  # WIP=1 检查：已有 active 则拒绝
│   │   ├── mark_passing(feature_id, evidence)  # 必须验证通过
│   │   ├── block(feature_id, reason)
│   │   └── 状态转换的 audit log
│   ├── get_next_action() → Optional[Feature]
│   │   # 最高优先级的 not_started 特性
│   └── VCR（Verified Completion Rate）计算
│       └── VCR = passed_count / started_count
│
├── wip.py               # WIPLimiter
│   ├── max_wip: int = 1  # 默认 WIP=1
│   ├── can_start_new() → bool
│   ├── current_active_count() → int
│   └── enforce() → raises WIPExceeded
│
├── evidence.py          # CompletionEvidence
│   ├── Evidence Types:
│   │   ├── CommandOutputEvidence  # "pytest 通过" 或 "curl returns 201"
│   │   ├── FileExistsEvidence    # "文件存在且非空"
│   │   └── CustomPredicateEvidence  # 自定义验证函数
│   ├── validate(evidence) → bool
│   └── "代码看起来没问题" 不算证据
│
├── handoff.py           # SessionHandoff
│   ├── generate_handoff(session_data) → handoff_markdown
│   │   # 生成 session-handoff.md
│   │   # 包含：当前状态、变更、仍存在的问题、下一步、命令参考
│   ├── clean_state_check() → CleanStateResult
│   │   # 5 条件检查：
│   │   # 1. 构建通过
│   │   # 2. 测试通过
│   │   # 3. 进度已记录
│   │   # 4. 无残留半成品
│   │   # 5. 启动路径可用
│   └── FreshSessionTest
│       └── 模拟新 agent：仅从仓库回答 5 个问题
│           ├── 这个系统是什么？
│           ├── 如何组织的？
│           ├── 如何运行？
│           ├── 如何验证？
│           └── 当前进度？
│
└── acid.py              # ACID 状态管理
    ├── AtomicityHelper
    │   └── logical_operation(context)  # 上下文管理器
    │       # 开始前 snapshot，失败时 git stash 回滚
    ├── ConsistencyChecker
    │   └── verify_predicates_after(op)  # 操作后验证
    ├── IsolationManager
    │   └── 多 agent 隔离的独立进度文件
    └── DurabilityWriter
        └── 关键知识写入 git 跟踪文件
```

**集成点**：
- `AgentRuntime.run()` 开始时 → `ProgressTracker.read_on_session_start()`
- `AgentRuntime.run()` 结束时 → `ProgressTracker.update_on_session_end()` + `SessionHandoff.generate_handoff()`
- `TodoTool` → 与 `FeatureListManager` 联动，WIP=1 约束
- `CheckpointManager` → 保存时包含 `ProgressSnapshot`
- `ReActLoop` → 每步更新 `ProgressTracker`

**配置模型**：

```python
class StateConfig(BaseModel):
    progress_file: str = "PROGRESS.md"
    feature_list_file: str = "feature_list.json"
    max_wip: int = 1
    acid_enabled: bool = True
    handoff_enabled: bool = True
    clean_state_check_on_exit: bool = True
```

**严重程度**：**P1 - 重要缺失**。没有项目级状态，跨会话的长任务无法可靠执行。

---

### 差距 3：WIP=1 工作流与任务边界

**课程核心观点**：Agent 天然倾向于同时做多件事（overreach），导致全都完不成。WIP=1 限制同时只有一个任务活跃，且完成需要可执行的完成证据。课程数据显示 WIP=1 将完成率从 37.5% 提升到 87.5%。

**当前状态**：
- TodoTool 没有 WIP 限制（多个任务可同时为 `in_progress`）
- 没有完成证据要求（没有 "curl returns 201" 级别的验证）
- 没有 VCR (Verified Completion Rate) 追踪
- 没有任务间的 DAG 依赖关系

**需要增强 TodoTool + 新增**：

```
增强 TodoTool + 新增：

├── WIPLimiter（见差距 2 的 wip.py）
│   ├── 严格模式：同一时间只能有 1 个 active 任务
│   ├── 宽松模式：允许 N 个 active 任务
│   └── 新任务激活前置条件：当前任务验证通过或显式暂停
│
├── CompletionEvidence（见差距 2 的 evidence.py）
│   ├── 每个任务关联验证命令
│   ├── 完成证据必须是可执行验证的输出
│   └── "代码看起来没问题" ≠ 完成证据
│
├── TaskDAG - 任务依赖图（新增）
│   ├── 任务间的 blocks/blockedBy 关系
│   └── 自动化的"下一步可做任务"推荐
│
└── VCRTracker - 验证完成率追踪（集成到 FeatureListManager）
    ├── VCR = passed tasks / started tasks
    ├── VCR < 1.0 时不允许开启新任务
    └── 趋势图：VCR 随时间的变化
```

**严重程度**：**P1 - 重要缺失**。

---

### 差距 4：指令子系统（指令架构与信噪比优化）

**课程核心观点**：AGENTS.md 是 agent 的"路由器"而非"百科全书"（50-200 行），遵循"高频信息在手，低频信息归档"原则。必须注意"Lost in the Middle"效应（Liu et al., 2023）。

**当前状态**：
- `ClaudemdSegment` 会加载 CLAUDE.md，但没有结构化约束
- `PromptBuilder` 有 6 个 segment，但没有信噪比优化
- 没有指令路由架构（router doc + topic docs）
- 没有针对"Lost in the Middle"的位置优化

**需要增强**：

```
增强模块：src/open_agent/prompt/

├── instruction_router.py   # InstructionRouter（新增）
│   ├── discover_topic_docs(project_root) → List[TopicDoc]
│   │   # 自动发现 docs/ 下的主题文档
│   ├── select_relevant_docs(task_domain, task_intent) → List[TopicDoc]
│   │   # 基于当前任务选择相关文档
│   ├── parse_agents_md(path) → AgentsMdStructure
│   │   # 解析 AGENTS.md 结构：概述/约束/链接
│   └── build_instruction_context(task) → str
│       # 构建指令上下文：AGENTS.md + 相关 topic docs
│
├── snr_optimizer.py        # SNR 优化器（新增）
│   ├── calculate_snr(instructions, task_context) → float
│   ├── optimize(instructions, token_budget, task_context) → optimized_instructions
│   │   # 信噪比优化：
│   │   # 1. 移除与当前任务无关的指令（修 bug 时移除部署指令）
│   │   # 2. Token 预算下按相关性排序
│   │   # 3. 冗余指令检测和合并
│   └── detect_redundancy(instructions) → List[RedundancyReport]
│
├── position_strategy.py    # 位置策略（新增）
│   ├── apply_lost_in_middle_strategy(instructions) → reordered
│   │   # "Lost in the Middle" 感知
│   │   # 重要约束放在开头或结尾
│   │   # 关键规则不埋在长文本中间
│   └── prioritize_constraints(constraints) → ordered
│       # 硬约束（≤15 条）放在最高优先级
│
└── 增强 segments.py 中的现有 segments
    ├── ClaudemdSegment → 支持 router + topic docs
    │   # 不再加载整个 CLAUDE.md
    │   # 而是根据任务选择相关部分 + topic docs
    ├── MemorySegment → 集成 ProgressSnapshot
    │   # 注入 PROGRESS.md 摘要到 prompt
    └── 新增 FeatureListSegment
        # 注入当前 feature_list 状态到 prompt
```

**集成点**：
- `PromptBuilder.build()` → 使用 `InstructionRouter` 选择相关指令
- `PromptBuilder.build()` → 通过 `SNROptimizer` 优化信噪比
- `ReActLoop` 每轮 → 动态调整指令上下文

**严重程度**：**P1 - 重要缺失**。

---

### 差距 5：上下文焦虑管理

**课程核心观点**：Agent 在感知上下文窗口快满时会"抢跑"——跳过验证、选择简单方案。Opus 和 Sonnet 的行为差异很大，harness 设计必须区分模型。

**当前状态**：
- `RuntimeMemory` 有滚动摘要压缩，但没有上下文焦虑检测
- 没有模型特定的上下文管理策略
- 没有检测 agent 的"抢跑行为"
- 没有显式的上下文重置机制

**需要新增**：

```
新增模块：src/open_agent/context/

├── __init__.py
├── anxiety_detector.py    # ContextAnxietyDetector
│   ├── 检测"抢跑"信号：
│   │   ├── 跳过验证步骤
│   │   ├── 选择简单方案而非最优方案
│   │   ├── 过早声明完成
│   │   └── 输出质量下降（更短的回答、更少的推理）
│   ├── token_usage_ratio() → float  # 已用/总量
│   ├── anxiety_score() → float      # 综合焦虑分数
│   └── should_reset() → bool        # 是否需要上下文重置
│
├── reset_manager.py       # ContextResetManager
│   ├── generate_handoff_artifacts() → HandoffArtifacts
│   │   # 生成完整的交接产物：
│   │   # - 当前任务状态
│   │   # - 已完成的步骤和证据
│   │   # - 未完成的工作
│   │   # - 关键决策和理由
│   │   # - 下一步行动
│   ├── perform_reset() → ResetResult
│   │   # 1. 保存交接产物
│   │   # 2. 清空上下文
│   │   # 3. 从持久化产物重建最小上下文
│   │   # 4. 验证新上下文的完整性
│   └── verify_handoff_completeness() → CompletenessReport
│
├── model_strategy.py      # ModelAwareContextStrategy
│   ├── get_strategy(model_id) → ContextStrategy
│   │   # Opus 类模型：
│   │   #   - 压缩为主（compaction sufficient）
│   │   #   - 较高的焦虑阈值
│   │   #   - 较晚触发重置
│   │   # Sonnet/Haiku 类模型：
│   │   #   - 定期重置（periodic reset needed）
│   │   #   - 较低的焦虑阈值
│   │   #   - 较早触发重置
│   └── ContextStrategy 结构：
│       ├── max_context_ratio: float
│       ├── anxiety_threshold: float
│       ├── prefer_compaction: bool
│       └── reset_interval: Optional[int]  # 每 N 轮重置
│
└── staleness.py           # StalenessManager
    ├── track_attention_quality() → AttentionScore
    │   # 跟踪 agent 是否还在关注早期的重要约束
    └── inject_reminder(constraints) → str
        # 在关键节点重新注入重要约束
```

**集成点**：
- `ReActLoop._think_and_act()` → 每轮检查 `ContextAnxietyDetector`
- `RuntimeMemory.add()` → 触发 `ModelAwareContextStrategy`
- `AgentRuntime.run()` → 当需要重置时调用 `ContextResetManager`

**严重程度**：**P1 - 重要缺失**。上下文焦虑是长任务失败的主要原因之一。

---

### 差距 6：初始化阶段

**课程核心观点**：初始化和实现有不同的优化目标。初始化最大化后续会话的可靠性；实现最大化功能产出。混合两者会导致都做不好。

**当前状态**：
- 没有独立的初始化阶段
- 没有启动就绪检查表
- 没有热启动模板系统
- Agent 直接进入任务执行

**需要新增**：

```
新增模块：src/open_agent/initialization/

├── __init__.py
├── readiness.py           # StartupReadinessChecker
│   ├── 4 条件检查：
│   │   ├── can_start()     # 环境可用（依赖已安装）
│   │   ├── can_test()      # 验证框架就绪（pytest/configured）
│   │   ├── can_see_progress()  # 进度文件存在（PROGRESS.md）
│   │   └── can_pick_up()   # 有明确的下一步任务
│   ├── check_all() → ReadinessReport
│   └── auto_fix() → FixResult  # 自动修复缺失项
│
├── hot_start.py           # HotStartManager
│   ├── 项目类型模板：
│   │   ├── PythonTemplate（pyproject.toml, pytest, ruff）
│   │   ├── NodeTemplate（package.json, jest, eslint）
│   │   └── CustomTemplate
│   ├── generate_scaffold(template, config) → GeneratedFiles
│   │   # 自动生成：
│   │   # - AGENTS.md / CLAUDE.md
│   │   # - init.sh
│   │   # - PROGRESS.md
│   │   # - feature_list.json
│   │   # - Makefile
│   └── detect_project_type(root) -> ProjectType
│
└── environment.py         # EnvironmentDescriber
    ├── scan_environment() → EnvironmentSnapshot
    │   # 检测：语言版本、包管理器、lock 文件、Dockerfile、CI 配置
    ├── verify_self_describing() → List[Gap]
    │   # 缺少 .python-version? 缺少 lock 文件?
    └── inject_to_prompt() → str
        # 将环境信息注入 DynamicEnvSegment
```

**严重程度**：**P2 - 中等缺失**。

---

### 差距 7：双层可观测性增强

**课程核心观点**：可观测性分两层——运行时可观测性（系统做了什么）+ 流程可观测性（为什么要接受这个变更）。当前只有前者。

**当前状态**：
- Trace/Span 系统覆盖了运行时可观测性
- 缺少流程可观测性（决策记录、为什么选方案 A 而非 B）
- 没有 Sprint Contract 概念
- 没有评分准则作为产物

**需要新增**：

```
新增模块：src/open_agent/observability/

├── __init__.py
├── decision_log.py        # DecisionLogger
│   ├── log_decision(decision, rationale, alternatives)
│   │   # 记录：为什么选 A 不选 B
│   ├── get_recent_decisions(n) → List[Decision]
│   └── inject_into_prompt() → str
│       # 将关键决策注入 prompt，避免 agent 重复考虑已否决的方案
│
├── sprint_contract.py     # SprintContractManager
│   ├── create_contract(scope, verification, exclusions) → Contract
│   │   # 编码前的短期协议
│   ├── verify_contract(contract) → ContractResult
│   └── contract_to_prompt() → str
│
├── review_elevation.py    # ReviewFeedbackElevation
│   ├── record_observation(observation: CodeReviewObservation)
│   ├── generate_check(observation) -> AutomatedCheck
│   │   # 将代码评审观察转化为自动化检查
│   │   # 例如："所有 API 路由必须有错误处理" → lint 规则
│   ├── get_active_checks() → List[AutomatedCheck]
│   └── auto_evolve()  # Harness 自动增强
│
└── quality_document.py    # QualityDocumentManager
    ├── update_quality_doc(session_result) -> QualitySnapshot
    │   # 每个维度的评分：
    │   # - 验证状态
    │   # - Agent 可读性
    │   # - 测试稳定性
    │   # - 架构边界合规性
    │   # - 代码标准遵循度
    ├── get_trend() -> QualityTrend  # 趋势：变强还是变弱？
    └── detect_drift() -> List[DriftAlert]  # 质量漂移检测
```

**严重程度**：**P2 - 中等缺失**。

---

### 差距 8：质量漂移检测与 Harness 简化

**课程核心观点**：熵增定律——没有主动维护，复杂度总是增加。OpenAI 的实验显示 agent 会复制已有模式即使它们不一致。需要定期测试 harness 组件是否仍然必要。

**当前状态**：
- 没有质量漂移检测
- 没有 harness 简化机制
- FeedbackLoop 生成回避提示，但没有系统化的质量追踪

**需要新增**：

```
新增：集成到 src/open_agent/observability/quality_document.py

├── QualityDriftDetector - 质量漂移检测
│   ├── 模式一致性检查（agent 是否在复制不一致的模式）
│   ├── 代码质量趋势追踪
│   └── 与质量文档的联动
│
├── HarnessSimplification - Harness 简化
│   ├── 每月测试：禁用一个组件 → benchmark
│   ├── 结果不退化 → 永久移除
│   └── 组件必要性追踪
│
└── CleanStateHandoff - 干净状态交接（见差距 2 的 handoff.py）
    ├── 5 条件检查（构建通过/测试通过/进度已记录/无残留/启动路径可用）
    ├── 会话结束前的强制检查
    └── 不满足 = 会话未"完成"
```

**严重程度**：**P2 - 中等缺失**。

---

## 第二部分实现路线图

```
Phase 1 — 反馈子系统（2-3 周）──────────────────────────────
│  课程核心观点：反馈子系统 ROI 最高
│
├── src/open_agent/verification/
│   ├── registry.py      # 验证命令注册
│   ├── runner.py        # 验证执行器
│   ├── parsers.py       # 结果解析器 + 面向 agent 的错误信息
│   ├── gate.py          # 验证门控
│   └── termination.py   # 三层终止检查
│
├── 修改 ReActLoop       # 集成 TerminationChecker
├── 修改 TodoTool        # 完成前强制验证
├── 修改 config.py       # 新增 VerificationConfig
└── tests/test_verification.py

Phase 2 — 状态子系统（1-2 周）──────────────────────────────
│  课程核心观点：没有项目级状态就没有跨会话可靠性
│
├── src/open_agent/state/
│   ├── progress.py      # ProgressTracker
│   ├── feature_list.py  # FeatureListManager
│   ├── wip.py           # WIPLimiter
│   ├── evidence.py      # CompletionEvidence
│   ├── handoff.py       # SessionHandoff
│   └── acid.py          # ACID 管理
│
├── 修改 AgentRuntime    # 启动/结束时集成进度跟踪
├── 修改 config.py       # 新增 StateConfig
└── tests/test_state.py

Phase 3 — 指令 + 上下文（1-2 周）──────────────────────────
│  课程核心观点：指令路由 + 上下文焦虑管理
│
├── src/open_agent/prompt/
│   ├── instruction_router.py  # 指令路由
│   ├── snr_optimizer.py       # 信噪比优化
│   └── position_strategy.py   # 位置策略
│
├── src/open_agent/context/
│   ├── anxiety_detector.py    # 上下文焦虑检测
│   ├── reset_manager.py       # 显式上下文重置
│   ├── model_strategy.py      # 模型感知策略
│   └── staleness.py           # 注意力衰减追踪
│
├── 修改 PromptBuilder   # 集成路由和 SNR 优化
├── 修改 ReActLoop       # 集成上下文焦虑检测
└── tests/test_context.py

Phase 4 — 初始化 + 可观测性（1-2 周）───────────────────────
│  课程核心观点：初始化独立于实现 + 双层可观测性
│
├── src/open_agent/initialization/
│   ├── readiness.py      # 启动就绪检查
│   ├── hot_start.py      # 热启动模板
│   └── environment.py    # 环境自描述
│
├── src/open_agent/observability/
│   ├── decision_log.py   # 决策记录
│   ├── sprint_contract.py # Sprint 契约
│   ├── review_elevation.py # 评审反馈提升
│   └── quality_document.py # 质量文档
│
└── tests/test_init.py, tests/test_observability.py
```

---

## 两部分的关系

```
┌──────────────────────────────────────────────────────────────┐
│  第一部分：Claude Code 的 Harness（开发环境）                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │CLAUDE.md │ │Makefile  │ │PROGRESS  │ │feature_  │       │
│  │          │ │make check│ │  .md     │ │list.json │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │            │            │            │               │
│       ▼            ▼            ▼            ▼               │
│  Claude Code 用这些文件可靠地开发 ↓                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  第二部分：Coding Agent 的 Harness（产品能力）       │    │
│  │                                                     │    │
│  │  ┌────────────┐ ┌───────────┐ ┌──────────────┐     │    │
│  │  │Verification│ │  State    │ │  Instruction │     │    │
│  │  │Subsystem   │ │Subsystem  │ │Subsystem     │     │    │
│  │  │(Phase 1)   │ │(Phase 2)  │ │(Phase 3)     │     │    │
│  │  └────────────┘ └───────────┘ └──────────────┘     │    │
│  │  ┌────────────┐ ┌───────────┐ ┌──────────────┐     │    │
│  │  │Context     │ │  Init     │ │Observability │     │    │
│  │  │Management  │ │Phase      │ │Enhancement   │     │    │
│  │  │(Phase 3)   │ │(Phase 4)  │ │(Phase 4)     │     │    │
│  │  └────────────┘ └───────────┘ └──────────────┘     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  第一部分的文件是 Claude Code 的 harness，                    │
│  也是第二部分要实现的"模板"——agent 要能为用户                   │
│  自动生成这些文件                                             │
└──────────────────────────────────────────────────────────────┘
```

**关键洞察**：第一部分（仓库文件）本身就是第二部分（agent 能力）的"狗粮"——你的 agent 要能自动生成 CLAUDE.md、PROGRESS.md、feature_list.json，而这些文件首先要在你自己的项目中存在和使用。
