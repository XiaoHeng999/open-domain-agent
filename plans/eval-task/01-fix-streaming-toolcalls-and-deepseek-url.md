# Issue 01: 修复 Streaming Tool_Calls 丢失 Bug + DeepSeek URL 统一

## Parent

PRD: `prd/02-PRD-eval-system-and-testing.md`

## What to build

修复两个已发现的 critical bug：

**Bug 1 — Streaming 模式丢弃 tool_calls：**
`OpenAIProvider._stream_openai()` 在流式迭代时只收集 text delta，最后返回 `tool_calls=[]`。需要在流式迭代中同时收集 `chunk.choices[0].delta.tool_calls`，按 index 聚合为完整 tool_call 对象（function name + arguments 拼接），流结束后转换为 `ToolCallResponse.tool_calls` 格式。确保与 non-streaming 路径使用相同的输出格式。

**Bug 2 — DeepSeek URL 默认值不一致：**
`DeepSeekProvider.__init__` 的 fallback URL 为 `https://api.deepseek.com`（无 `/v1`），而 config.yaml 使用 `https://api.deepseek.com/v1`。OpenAI SDK 不会自动补版本路径，导致无 config 时请求错误 endpoint。将代码默认值改为 `https://api.deepseek.com/v1`。

完成后补充对应的单元测试，确保 `make check` 通过。

## Acceptance criteria

- [ ] `_stream_openai()` 在流式模式下正确收集 tool_calls（function name + arguments 完整拼接）
- [ ] streaming 和 non-streaming 模式返回相同格式的 `ToolCallResponse`
- [ ] `DeepSeekProvider` 无 config 时 fallback URL 为 `https://api.deepseek.com/v1`
- [ ] 新增 streaming + tool_calls 单元测试（mock streaming chunks，验证 tool_calls 正确收集）
- [ ] 新增 DeepSeek URL fallback 单元测试
- [ ] `pytest tests/ -x -q` 全部通过
- [ ] `make check` 全部通过

## Blocked by

None — can start immediately.

## User stories

- #1: streaming 模式下 agent 能调用工具
- #2: DeepSeek URL 默认值与 config.yaml 一致
- #3: streaming/non-streaming 模式行为一致
