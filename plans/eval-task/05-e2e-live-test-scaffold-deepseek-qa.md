# Issue 05: E2E Live 测试骨架 + DeepSeek 简单问答验证

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

建立 E2E live 测试基础设施，并用最简单的场景验证 DeepSeek provider 端到端可用。

1. 在 `pyproject.toml` 的 pytest 配置中注册 `@pytest.mark.live` marker，并添加 `markers = ["live: marks tests as live E2E (requires API key)"]`
2. 创建 `tests/test_e2e_live.py`，包含基础 fixture（从环境变量读取 API key、创建 AgentRuntime）
3. 编写第一个 live 测试：真实 DeepSeek 简单问答（"What is 1+1?"），验证 output 包含 "2"
4. 所有 live 测试用 `@pytest.mark.live` 标记，无 `DEEPSEEK_API_KEY` 环境变量时 `skipif` 跳过

此 slice 是后续所有 live 测试（Issue 06-09）的骨架。

## Acceptance criteria

- [ ] `pyproject.toml` 注册 `live` pytest marker
- [ ] `tests/test_e2e_live.py` 存在，包含 live fixture 和第一个测试
- [ ] 无 API key 时 `pytest tests/` 正常跳过 live 测试（不 fail）
- [ ] 设置 `DEEPSEEK_API_KEY` 后 `pytest tests/test_e2e_live.py -m live -v` 通过
- [ ] 真实 DeepSeek 响应包含预期内容
- [ ] `make check`（不含 live）正常通过

## Blocked by

- Issue 01: 修复 streaming bug（需要 bug 修复后才能正确跑真实场景）

## User stories

- #11: 有 `@pytest.mark.live` 标记的 E2E 测试
- #12: 验证 DeepSeek provider 链路端到端可用

## Notes

**Type: HITL** — 需要人工提供 `DEEPSEEK_API_KEY` 环境变量才能执行。
