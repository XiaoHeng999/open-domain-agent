## 1. 移除 General 预设

- [x] 1.1 从 `src/open_agent/subagent/presets.py` 的 BUILTIN_PRESETS 字典中删除 "general" 条目
- [x] 1.2 修改 `src/open_agent/subagent/manager.py` 的 `get_preset()` 方法，将 fallback 从 "general" 改为 "explore"
- [x] 1.3 修改 `src/open_agent/tools/subagent.py` 的 `subagent_type` 参数默认值从 "general" 改为 "explore"

## 2. 新增 Researcher 预设

- [x] 2.1 在 `src/open_agent/subagent/presets.py` 的 BUILTIN_PRESETS 中新增 "researcher" 预设条目（工具集：web_search, web_fetch, search, read_file, list_dir；max_turns=25）

## 3. 优化现有预设的 System Prompt 和工具集

- [x] 3.1 优化 "explore" 预设：增强 system_prompt（角色定义+工作流程+输出格式），添加 "search" 到 allowed_tools
- [x] 3.2 优化 "plan" 预设：增强 system_prompt（角色定义+计划模板+输出格式），添加 "search" 到 allowed_tools
- [x] 3.3 优化 "code-reviewer" 预设：增强 system_prompt（角色定义+审查维度 checklist+结构化报告格式）
- [x] 3.4 优化 "code-writer" 预设：增强 system_prompt（角色定义+编码准则+工作流程+验证要求）

## 4. 更新工具描述

- [x] 4.1 更新 `src/open_agent/tools/subagent.py` 中 SubagentTool 的 description，列出所有内置 preset（explore, plan, code-reviewer, code-writer, researcher）及其适用场景，移除 general 相关描述

## 5. 验证

- [x] 5.1 运行现有测试确保 subagent 相关功能正常（`python -m pytest tests/ -k subagent`）
- [x] 5.2 验证 merge_presets 逻辑对移除 general 后的行为正确（用户覆盖、新预设添加）
