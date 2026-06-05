# Issue 09: E2E — 跑通完整 Smoke Eval Suite

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在 `tests/test_e2e_live.py` 中添加 E2E 测试，通过 EvalRunner 跑完整个 `evals/smoke/` suite 的全部 7 个 scenario，验证完整流程：加载 YAML → 创建 AgentRuntime → 逐个执行 scenario → 检查 expectations → 生成报告。

同时验证 CLI 命令 `agent eval --suite smoke --dir evals` 在真实 DeepSeek 下能输出完整的 Rich table 报告。

## Acceptance criteria

- [ ] E2E 测试跑完 evals/smoke/ 全部 7 个 scenario
- [ ] 每个 scenario 返回 pass 或 fail 状态（不 crash）
- [ ] EvalRunner 正确检查 expected_tools 和 expected_outcome
- [ ] CLI `agent eval --suite smoke --dir evals` 输出完整 Rich table 报告
- [ ] `pytest tests/test_e2e_live.py -m live -v` 通过（需要 API key）

## Blocked by

- Issue 03: CLI eval 接通 runtime
- Issue 05: E2E live 测试骨架
- Issue 02: evals/smoke/ YAML 文件（测试对象）

## User stories

- #16: 一次性获得所有核心路径的验证报告

## Notes

**Type: HITL** — 需要 `DEEPSEEK_API_KEY`。
