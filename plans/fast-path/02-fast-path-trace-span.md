# 02: Fast Path Trace Span

## Type
AFK

## Parent

PRD-05: Fast Path 优化 — 简单请求跳过 ReAct 循环

## What to build

在 fast path 分支中创建轻量 trace span（名称 `fast_path`，kind=AGENT_LOOP），记录 intent、domain、answer_len 属性后 finish。确保 fast path 请求在 trace 系统中留有记录，方便排查"为什么这个请求没走 ReAct"。

## Acceptance criteria

- [ ] fast path 创建 `fast_path` span（kind=AGENT_LOOP）
- [ ] span 记录 `intent`、`domain`、`answer_len` 属性
- [ ] span 在返回前正确 finish
- [ ] trace 为 None 时不报错（跳过 span 创建）
- [ ] `pytest tests/ -x -q` 全量通过

## User stories covered

- US 5: 简单请求在 trace 中留有记录

## Blocked by

- 01: Fast Path 核心分支
