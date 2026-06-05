# Issue 04: Eval 结果持久化

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

在 EvalRunner 的 `run_suite()` 方法中添加结果持久化。每次跑完一个 suite 后，将完整结果保存到 `.open_agent/eval_results/<suite>_<timestamp>.json`。

结果 JSON 结构：
```json
{
  "suite": "smoke",
  "timestamp": "2026-06-03T14:30:00",
  "model": {"provider": "deepseek", "name": "deepseek-chat"},
  "results": [
    {"name": "...", "status": "pass/fail", "checks": [...], "output": "..."}
  ],
  "summary": {"total": 7, "passed": 6, "failed": 1}
}
```

目录不存在时自动创建。完成后补充持久化测试：验证文件写入、JSON 结构正确、多次运行产生不同时间戳文件。

## Acceptance criteria

- [ ] `run_suite()` 完成后自动将结果保存到 `.open_agent/eval_results/` 目录
- [ ] 文件名格式为 `<suite>_<ISO-timestamp>.json`
- [ ] JSON 结构包含 suite、timestamp、model、results、summary 五个顶层字段
- [ ] 目录不存在时自动创建（不报错）
- [ ] 新增持久化单元测试验证文件写入和结构
- [ ] `pytest tests/ -x -q` 全部通过

## Blocked by

- Issue 03: CLI eval 接通 runtime（持久化依赖 runner-runtime 集成）

## User stories

- #9: eval 结果以 JSON 持久化，可比较不同时间跑分
- #10: 结果记录包含完整信息可追溯历史表现
