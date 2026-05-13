## Why

当前内置的 5 个 subagent 预设（explore, plan, code-reviewer, code-writer, general）存在以下问题：
1. `general` 预设职责模糊，不符合"专业分工"的 subagent 设计原则，应移除
2. 缺少 `researcher`（信息研究）子代理，无法高效处理需要 Web 搜索+整合分析的任务
3. 现有预设的 system_prompt 过于简短，缺少结构化输出指导和行为约束，与行业最佳实践（Claude Code、pi-mono、nanobot）的 prompt 质量有差距
4. `explore` 预设缺少 `search`（ripgrep）工具，无法高效进行代码搜索

## What Changes

- **BREAKING**: 移除 `general` 预设类型，`SubagentTool` 的 `subagent_type` 默认值从 `"general"` 改为 `"explore"`
- 新增 `researcher` 预设类型（Web 信息搜索+整合分析，只读）
- 优化 `explore` 预设：增强 prompt 结构、添加 `search` 工具
- 优化 `plan` 预设：增强 prompt 结构，要求输出结构化计划模板
- 优化 `code-reviewer` 预设：增强 prompt 结构，增加分类审查 checklist
- 优化 `code-writer` 预设：增强 prompt 结构，增加编码准则和验证流程
- 更新 `SubagentManager.get_preset()` 的 fallback 行为：未知类型 fallback 到 `"explore"` 而非 `"general"`

## Capabilities

### New Capabilities
- `researcher-preset`: 新增 researcher 子代理预设，专注于 Web 信息搜索、文档查阅和整合分析

### Modified Capabilities
- `subagent-presets`: 移除 general 预设、优化 explore/plan 的 prompt 和工具集
- `subagent-specialized-presets`: 优化 code-reviewer/code-writer 的 prompt 结构
- `subagent-tool`: SubagentTool 的默认 subagent_type 从 "general" 改为 "explore"

## Impact

- `src/open_agent/subagent/presets.py`: BUILTIN_PRESETS 字典修改、merge_presets 逻辑不变
- `src/open_agent/subagent/manager.py`: get_preset() fallback 逻辑修改
- `src/open_agent/tools/subagent.py`: 默认 subagent_type 参数修改
- `openspec/specs/subagent-presets/spec.md`: 更新 explore/plan 需求、移除 general 需求
- `openspec/specs/subagent-specialized-presets/spec.md`: 更新 code-reviewer/code-writer prompt 需求
- `openspec/specs/subagent-tool/spec.md`: 更新默认 subagent_type 需求
