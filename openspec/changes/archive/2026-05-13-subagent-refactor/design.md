## Context

当前系统有 5 个内置 subagent 预设（explore, plan, code-reviewer, code-writer, general）。基于对 pi-mono（session trees）、nanobot（Agent Kernel 7 子系统）、Claude Code（Explore/Plan/General-purpose/自定义）等行业实践的分析，需要进行以下调整：

- 每个 subagent 应有清晰的职责边界和专业化的 prompt
- prompt 应包含：角色定义、行为约束、输出格式、工具使用指南
- `general` 预设与"专业分工"原则冲突，主 agent 本身就是 general-purpose
- 缺少 `researcher` 类型用于需要深度 Web 搜索和信息整合的场景

## Goals / Non-Goals

**Goals:**
- 移除 `general` 预设，将默认 subagent_type 改为 `explore`
- 新增 `researcher` 预设（Web 搜索+文档整合，只读）
- 优化所有 5 个预设的 system_prompt，增加结构化输出指导
- 给 `explore` 预设添加 `search` 工具

**Non-Goals:**
- 不修改 SubagentPreset/SubagentResult 数据结构
- 不修改 SubagentManager 的并发控制和生命周期管理
- 不新增工具类（所有需要的工具已存在）
- 不修改 ReActLoop 核心

## Decisions

### 1. 移除 general 预设，默认改为 explore
- **理由**: 主 agent 已经是 general-purpose，subagent 存在的意义是专业化。general 预设让 LLM 倾向于选择它作为"万能选项"，削弱了预设类型系统的价值
- **替代方案**: 保留 general 但限制工具 → 仍违反专业分工原则
- **影响**: `SubagentTool` 的 `subagent_type` 默认值改为 `"explore"`；`get_preset()` 的 fallback 改为 `"explore"`

### 2. 新增 researcher 预设
- **工具集**: `web_search`, `web_fetch`, `search`, `read_file`, `list_dir`（只读）
- **max_turns**: 25（研究任务可能需要多轮搜索）
- **理由**: 信息研究是独立于代码探索的专业能力，需要不同的 prompt 指导（来源标注、信息交叉验证、偏见识别等）

### 3. Prompt 结构化模板
每个 prompt 遵循统一结构：
1. **角色定义**（1-2 句，你是谁）
2. **行为约束**（MUST/MUST NOT 规则）
3. **工作流程**（步骤序列）
4. **输出格式**（期望的输出结构）
5. **工具指南**（如何高效使用可用工具）

### 4. explore 预设添加 search 工具
- **理由**: 当前 explore 只有 `read_file`, `list_dir`, `web_search`, `web_fetch`，缺少 `search`（ripgrep grep/glob）。代码探索的核心能力就是搜索，缺少 search 工具严重限制了探索效率

## Risks / Trade-offs

- **[Breaking] 移除 general 预设** → 已有用户 config 如果引用 `subagent_type="general"` 将触发 fallback 到 explore，并打印 warning。这是可接受的，因为 general 本身就是"万能"的，explore 是最安全的 fallback
- **[Token 膨胀] 更长的 prompt** → 新 prompt 比旧 prompt 长约 2-3x（从 ~50 words 到 ~150 words）。trade-off 可接受，因为 prompt 质量直接决定 subagent 输出质量
- **[研究成本] researcher 的 max_turns=25** → 研究任务可能消耗较多 token。这是必要的，因为 Web 搜索需要多轮交互
