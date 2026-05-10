## Context

当前 open_agent 框架的系统提示词构建逻辑分散在 5+ 个模块中：
- `ReActLoop._build_messages()` 使用硬编码 `"You are a helpful agent using the ReAct framework."`
- `DomainRouter` 中每个 domain 内嵌 system_prompt
- `SkillMatcher.get_skills_for_prompt()` 返回匹配技能内容但未注入 ReAct 消息
- `PlanGenerator` 和 `IntentParser` 各有独立 system prompt

这些模块之间没有统一的组装机制。路由决策产出的 domain system prompt 和技能内容被计算后丢弃，从未进入 LLM 调用。同时，逻辑 agent 分层需要不同角色拥有不同工具集，但当前 ToolRegistry 是全局共享的。

## Goals / Non-Goals

**Goals:**
- 建立统一的 Prompt Assembly Pipeline，将 6 类上下文信息按语义段组装为完整 system prompt
- 区分稳定段（启动时生成一次）和动态段（每轮刷新），减少重复 token 消耗
- 为逻辑 agent 分层提供工具列表动态注入能力
- 扩展 Skills 系统支持 Python handler + Markdown 定义双文件结构
- 创建 5 个新技能包的文件结构骨架

**Non-Goals:**
- 不实现 token 预算动态分配（后续优化）
- 不实现提示词版本管理或 A/B 测试
- 不修改 LLM provider 层的调用接口
- 不实现 skills 的自动安装/卸载（仅手动放置文件）
- 5 个新技能的 Markdown 指令内容暂由用户后续补充，本次只建骨架

## Decisions

### Decision 1: Pipeline 采用 Builder 模式 + Segment 抽象

**选择**: 定义 `PromptSegment` 基类和 6 个具体子类（`CoreIdentitySegment`, `ToolListSegment`, `SkillsSegment`, `MemorySegment`, `ClaudemdSegment`, `DynamicEnvSegment`），由 `PromptBuilder` 按固定顺序调用。

**理由**: 每个段有独立的稳定/动态属性和更新频率，Builder 模式让各段独立演化而不互相耦合。

**备选**: 单一函数拼接——可读性差，难以对各段独立测试和缓存。

### Decision 1.5: 提示词模板集中管理到 prompt.py

**选择**: 所有提示词文本模板（各段的静态模板字符串、分隔符模板、默认角色定义等）集中存放在 `src/open_agent/prompt/prompt.py` 中。各 Segment 类从该文件导入模板，自身不包含任何硬编码提示词字符串。

**理由**: 提示词是迭代最频繁的部分。集中管理后：(1) 调优提示词只需改一个文件；(2) 支持未来 i18n / 提示词版本切换；(3) 避免"提示词分散在各模块中"的现状问题重现。

**文件结构**:
```
src/open_agent/prompt/
  __init__.py        # 模块入口，导出 PromptBuilder
  prompt.py          # 所有提示词模板常量集中定义
  segments.py        # 6 个 Segment 类（从 prompt.py 导入模板）
  builder.py         # PromptBuilder 组装逻辑
```

`prompt.py` 内容组织：
```python
# ── 段分隔符 ──
SEGMENT_SEPARATOR = "\n\n---\n\n"

# ── 核心身份段模板 ──
CORE_IDENTITY_TEMPLATE = "..."
CORE_IDENTITY_CUSTOM_TEMPLATE = "..."

# ── 工具列表段模板 ──
TOOL_LIST_HEADER = "..."
TOOL_ENTRY_TEMPLATE = "..."

# ── Skills 段模板 ──
SKILLS_HEADER = "..."
SKILL_ENTRY_TEMPLATE = "..."

# ── Memory 段模板 ──
MEMORY_HEADER = "..."
MEMORY_WORKING_TEMPLATE = "..."
MEMORY_EPISODIC_TEMPLATE = "..."
MEMORY_PROFILE_TEMPLATE = "..."

# ── CLAUDE.md 段模板 ──
CLAUDEMD_HEADER = "..."

# ── 动态环境段模板 ──
DYNAMIC_ENV_TEMPLATE = "..."
```

### Decision 2: 段分隔符与精简输出

**选择**: 每个 Segment 的 build() 输出以 `<segment_header>` + 实际内容 + 空行的格式返回。段与段之间用固定分隔符 `SEGMENT_SEPARATOR` 连接。

**分隔符格式** — 每个 Segment 输出结构：
```
<segment_type>  ← 段类型标记（如 <core_identity>, <tool_list>, <skills> 等）
{精简内容}
</segment_type>  ← 段结束标记（如 </core_identity>, </tool_list>, </skills> 等）
```

**精简原则**:
- 每段内容力求精简，避免冗余描述词
- 工具列表段：只输出 name + description + parameters（省略 JSON Schema 冗余字段）
- Skills 段：只输出技能名 + 指令正文（省略元数据重复）
- Memory 段：按"最新 N 条 + 摘要"格式压缩
- 空段跳过：不输出任何内容，包括分隔标记

**理由**: XML-style 标记让 LLM 更容易区分各段边界，也让调试时能快速定位某段内容。精简输出减少 token 浪费。

### Decision 3: 稳定段使用缓存，动态段每轮重建

**选择**: Segment 基类提供 `is_stable: bool` 属性。`PromptBuilder.build()` 时，stable segment 仅在首次调用或 `invalidate()` 时重新生成，dynamic segment 每次调用都重建。

**分段策略**:
| 段 | 类型 | 刷新时机 |
|---|---|---|
| Core Identity | 稳定 | 启动时 / 配置变更 |
| Tool List | 动态 | 工具集变更（逻辑 agent 切换） |
| Skills Metadata | 动态 | 技能匹配变化 |
| Memory Content | 动态 | 每轮对话 |
| CLAUDE.md Directives | 稳定+动态 | 文件变更时 / 新增项目指令 |
| Dynamic Environment | 动态 | 每轮对话 |

### Decision 4: 逻辑 agent 分层通过 ToolRegistry 快照实现

**选择**: `ToolRegistry` 新增 `snapshot()` / `restore()` / `filter_by_tags()` 方法。逻辑 agent 切换时，Pipeline 调用 `filter_by_tags(agent_role)` 生成当前角色的工具子集，`ToolListSegment` 只渲染该子集的 Schema。

**理由**: 避免为每个 agent 角色创建独立的 ToolRegistry 实例，保持全局注册表单一数据源。

**备选**: 每个逻辑 agent 持有独立 ToolRegistry——注册/注销复杂，工具状态不一致风险高。

### Decision 5: 技能包采用目录结构（skill_name/ 包含 .md + .py）

**选择**: 每个技能为一个目录，包含 `skill_name.md`（YAML frontmatter + 指令内容）和 `skill_name.py`（Python handler，导出 `register(registry: ToolRegistry)` 函数）。

**目录结构**:
```
src/open_agent/skills/builtin/
  code-review.md          # 现有格式保持不变
  skill-creator/
    skill-creator.md      # YAML frontmatter + 指令
    skill-creator.py      # handler: register() 函数
  summarize/
    summarize.md
    summarize.py
  weather/
    weather.md
    weather.py
  github/
    github.md
    github.py
  wechat-mp-cn/
    wechat-mp-cn.md
    wechat-mp-cn.py
```

**理由**: 单文件技能（现有格式）和目录技能（新格式）共存，向后兼容。Python handler 让技能可以注册自己的工具到 ToolRegistry。

### Decision 6: ReActLoop 通过 PromptBuilder 接收 system prompt

**选择**: `ReActLoop` 构造时接收 `PromptBuilder` 实例而非硬编码 system prompt。`_build_messages()` 调用 `builder.build(context)` 获取完整 system prompt。

**理由**: 最小化对 ReActLoop 的侵入性修改，仅替换一行硬编码。

## Risks / Trade-offs

- **[Token 溢出风险]** → 6 段拼接可能超出上下文窗口。缓解：各段提供 `estimate_tokens()` 方法，Pipeline 在 build 时检查总量并截断低优先级段。
- **[缓存一致性问题]** → 稳定段缓存可能与实际状态不同步。缓解：所有修改稳定段的操作必须调用 `builder.invalidate(segment_type)`。
- **[技能 handler 安全性]** → Python handler 文件可执行任意代码。缓解：技能 handler 运行在沙箱环境中，受 SafetyManager 管控。
- **[向后兼容]** → 现有单文件技能不受影响，目录技能为新增格式。缓解：`SkillParser` 自动检测文件/目录并选择对应解析路径。
