# Issue 02: 创建 evals/smoke/ YAML Scenario 文件

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

创建 `evals/smoke/` 目录，编写 7 个 YAML scenario 文件，覆盖 agent 的七大核心功能路径。每个 YAML 遵循 EvalRunner 已支持的 schema：`name`、`input`、`expected_tools`、`expected_outcome`。

七个 scenario：
1. **simple_qa** — 简单问答（"1+1等于几？"），无工具调用，期望输出含 "2"
2. **tool_read** — 读文件（"Read the contents of /etc/hostname"），期望调用 `read_file`
3. **tool_shell** — Shell 命令（"Run ls in /tmp"），期望调用 `shell_exec`
4. **tool_search** — 搜索（"Search for Python asyncio tutorial"），期望调用 `web_search`
5. **multi_step** — 多步推理（"Read /etc/hostname and tell me the OS"），期望调用 `read_file`
6. **chinese_input** — 中文输入（"请用中文解释什么是 ReAct"），无工具调用，期望输出含 "ReAct"
7. **self_tool** — Self 工具（"What tools do you have?"），期望调用 `self_inspect`

完成后验证 `agent eval --suite smoke --dir evals` 能加载并显示 scenario 列表。

## Acceptance criteria

- [ ] `evals/smoke/` 目录存在且包含 7 个 YAML 文件
- [ ] 每个 YAML 文件包含 `name`、`input` 字段（EvalRunner 要求的最小 schema）
- [ ] `agent eval --suite smoke --dir evals` 成功加载并显示 scenario 列表（无 runtime 时降级显示）
- [ ] YAML 文件均为有效的 `yaml.safe_load()` 可解析格式

## Blocked by

None — can start immediately. 可与 Issue 01 并行执行。

## User stories

- #4: 有预定义的 smoke scenario 快速验证 agent 功能
- #5: scenario 覆盖七大核心路径
- #6: scenario 按 suite 分组存放
