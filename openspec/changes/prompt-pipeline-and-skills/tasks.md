## 1. Prompt Pipeline 基础架构

- [ ] 1.1 创建 `src/open_agent/prompt/__init__.py` 模块入口
- [ ] 1.2 创建 `src/open_agent/prompt/prompt.py` — 集中定义所有提示词模板常量（SEGMENT_SEPARATOR、各段模板字符串、分隔标记名称等）
- [ ] 1.3 实现 `src/open_agent/prompt/segments.py` — 定义 PromptSegment 基类（含 is_stable 属性、build() 方法、estimate_tokens() 方法）和 SegmentType 枚举，所有模板从 prompt.py 导入
- [ ] 1.4 实现 `src/open_agent/prompt/builder.py` — PromptBuilder 类，管理 6 个段实例，支持 build() 组装、invalidate() 缓存失效、token 预算检查

## 2. 六个 Prompt Segment 实现

- [ ] 2.1 实现 CoreIdentitySegment — 从 prompt.py 导入 CORE_IDENTITY_TEMPLATE，从配置加载 Agent 角色定义和行为准则（稳定段）
- [ ] 2.2 实现 ToolListSegment — 从 prompt.py 导入 TOOL_LIST_HEADER / TOOL_ENTRY_TEMPLATE，渲染精简的工具描述（name + description + parameters），支持 tag 过滤（动态段）
- [ ] 2.3 实现 SkillsSegment — 从 prompt.py 导入 SKILLS_HEADER / SKILL_ENTRY_TEMPLATE，注入精简的技能名 + 指令正文（动态段）
- [ ] 2.4 实现 MemorySegment — 从 prompt.py 导入 MEMORY_HEADER 等模板，按"最新 N 条 + 摘要"格式组装 WorkingMemory、EpisodicStore、UserProfileState（动态段）
- [ ] 2.5 实现 ClaudemdSegment — 从 prompt.py 导入 CLAUDEMD_HEADER，加载全局和项目级 CLAUDE.md 指令文件（混合段）
- [ ] 2.6 实现 DynamicEnvSegment — 从 prompt.py 导入 DYNAMIC_ENV_TEMPLATE，输出当前日期时间、平台、工作目录等环境信息（动态段）

## 3. ToolRegistry 扩展

- [ ] 3.1 在 `src/open_agent/registry.py` 中添加 `snapshot()` 方法 — 返回当前工具名称的 frozenset
- [ ] 3.2 添加 `restore(snapshot)` 方法 — 恢复到快照时的工具集状态
- [ ] 3.3 添加 `filter_by_tags(tags)` 方法 — 返回匹配标签的工具条目列表

## 4. ReActLoop 集成

- [ ] 4.1 修改 `src/open_agent/agent/react.py` 的 ReActLoop 构造函数，接收 PromptBuilder 实例参数
- [ ] 4.2 修改 `_build_messages()` 方法，调用 `builder.build(context)` 替代硬编码 system prompt；移除 react.py 中所有内联提示词字符串
- [ ] 4.3 修改 `src/open_agent/runtime.py` 的 AgentRuntime，在初始化时创建 PromptBuilder 并注入 ReActLoop

## 5. Skills 系统扩展 — 目录技能包支持

- [ ] 5.1 修改 `src/open_agent/skills/parser.py`，添加目录技能解析逻辑（检测目录结构，分别解析 .md 和 .py）
- [ ] 5.2 修改 `src/open_agent/skills/registry.py`，在注册目录技能时自动加载并调用 .py handler 的 register() 函数
- [ ] 5.3 修改 `src/open_agent/skills/builtin/` 扫描逻辑，支持同时发现单文件技能和目录技能包

## 6. 新技能包骨架创建

- [ ] 6.1 创建 `src/open_agent/skills/builtin/skill-creator/` 目录，包含 `skill-creator.md`（YAML frontmatter 骨架）和 `skill-creator.py`（register 函数骨架）
- [ ] 6.2 创建 `src/open_agent/skills/builtin/summarize/` 目录，包含 `summarize.md` 和 `summarize.py`
- [ ] 6.3 创建 `src/open_agent/skills/builtin/weather/` 目录，包含 `weather.md` 和 `weather.py`
- [ ] 6.4 创建 `src/open_agent/skills/builtin/github/` 目录，包含 `github.md` 和 `github.py`
- [ ] 6.5 创建 `src/open_agent/skills/builtin/wechat-mp-cn/` 目录，包含 `wechat-mp-cn.md` 和 `wechat-mp-cn.py`

## 7. 测试

- [ ] 7.1 编写 `tests/test_prompt_pipeline.py` — 测试 PromptBuilder 组装、缓存、失效、token 估算、段分隔符格式
- [ ] 7.2 编写 `tests/test_prompt_segments.py` — 测试各 Segment 的 build() 输出和稳定/动态属性
- [ ] 7.3 编写 `tests/test_skill_extensions.py` — 测试目录技能包的发现、解析和 handler 注册
- [ ] 7.4 更新 `tests/test_registry.py` — 添加 snapshot/restore/filter_by_tags 测试
