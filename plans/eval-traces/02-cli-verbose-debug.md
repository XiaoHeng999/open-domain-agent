# Issue 02: CLI --verbose/--debug 标志

## What to build

为 CLI 添加全局 `--verbose` / `--debug` 标志，控制调试信息的显示。默认情况下，trace ID、steps、duration 等调试信息不显示。只有开启 `--verbose` 或 `--debug` 时才展示。

端到端行为：
- `agent run "hello"` — 不显示 trace 信息，只显示 Answer
- `agent run "hello" --verbose` — 显示 `Trace: xxx | Steps: x | Duration: xxxms`
- `agent run "hello" --debug` — 等同于 --verbose + 设置 logging level 为 DEBUG
- `agent chat` / `agent chat --verbose` — 同样行为

## Acceptance criteria

- [ ] Typer callback 注册全局 `--verbose` / `--debug` 选项
- [ ] `run` 命令中的 trace 显示块（当前行 70-74）被 `if _verbose:` 包裹
- [ ] `chat` 命令中的 trace 显示块（当前行 135-139）被 `if _verbose:` 包裹
- [ ] `--debug` 隐含 `--verbose`，并调用 `setup_structured_logging(level=logging.DEBUG)`
- [ ] 无 --verbose 时运行命令，确认不显示 trace 信息
- [ ] 有 --verbose 时运行命令，确认显示 trace 信息
- [ ] 现有测试不受影响

## Blocked by

None — 可立即开始

## User stories

- #3 普通用户不希望看到 trace ID 和调试信息
- #4 开发者希望通过 --verbose 或 --debug 控制调试信息显示
