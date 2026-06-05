# Issue 11: 边界条件测试 — Cancellation + ReAct + DeepSeek

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

为 cancellation、ReAct 循环、DeepSeek provider 补充边界条件测试：

### Cancellation 边界（补充到 `tests/test_task_cancellation.py`）
1. **多层嵌套取消**：外层和内层同时触发 cancel，验证不 deadlock
2. **Cancel 后 restart**：取消后重新使用 CancellationToken，验证状态正确重置
3. **取消时无进行中的任务**：cancel 空闲状态，验证无副作用

### ReAct 边界（补充到 `tests/test_agent.py` 或新建）
4. **max_iterations 达上限**：agent 循环达到最大迭代次数，验证优雅退出和部分结果
5. **工具报错恢复**：工具执行抛异常，验证 recovery strategy 生效且 agent 不 crash
6. **空工具响应**：工具返回空字符串，验证 agent 能继续推理

### DeepSeek 边界（补充到 `tests/test_provider_hardening.py`）
7. **API 错误响应**：DeepSeek 返回非 200 状态码，验证 tenacity 重试和最终错误上报
8. **Rate limit (429)**：DeepSeek 返回 rate limit，验证重试策略正确触发
9. **超时响应**：模拟超时，验证超时错误正确传播

所有测试使用 mock，不需要真实 API 调用。

## Acceptance criteria

- [ ] 新增至少 3 个 cancellation 边界测试
- [ ] 新增至少 3 个 ReAct 边界测试
- [ ] 新增至少 3 个 DeepSeek provider 边界测试
- [ ] `pytest tests/ -x -q` 全部通过
- [ ] `make check` 全部通过

## Blocked by

- Issue 01: streaming bug 修复（部分测试依赖修复后的代码）

## User stories

- #18: 多层嵌套取消、cancel 后 restart 等边界测试
- #19: ReAct max_iterations 达上限、工具报错恢复等边界测试
- #20: DeepSeek API 错误响应、rate limit 重试等边界测试
