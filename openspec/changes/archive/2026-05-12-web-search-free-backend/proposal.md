## Why

当前 `web_search` 工具硬绑定 Brave Search API（付费第三方服务），未配置 API Key 时工具仍然注册到 ToolRegistry 中，导致 LLM 选择了一个注定失败的工具，在 ReAct 循环中反复重试 10 轮后耗尽迭代次数，最终返回 fallback 文案。这使得搜索能力在默认配置下完全不可用，严重影响 Agent 的实用价值。参考 Claude Code 的做法（平台不支持 server-side search 时直接隐藏工具），我们应采用免费搜索后端（DuckDuckGo）作为默认兜底，确保开箱即用，同时遵循"不可用就不暴露"原则。

## What Changes

- 新增 `DuckDuckGoSearchTool`，使用 `duckduckgo-search` 库（免费、无需 API Key）作为默认搜索后端
- **BREAKING** `scan_builtin_tools` 注册逻辑从"无条件注册所有工具"改为"按后端可用性注册"：有 API Key 注册 Brave，否则注册 DuckDuckGo，都不可用则不注册搜索工具
- `WebSearchTool` 重命名为 `BraveSearchTool` 以明确语义，保留作为可选后端
- `WebFetchTool` 返回内容从原始 HTML 改为 Markdown 格式，提升 LLM 可读性
- `react.py` 中 `success` 判断从 `content.startswith("Error:")` 字符串匹配改为结构化判断

## Capabilities

### New Capabilities
- `web-search-backends`: 多后端搜索架构，支持 DuckDuckGo（免费默认）和 Brave Search（付费可选），按可用性自动选择后端注册

### Modified Capabilities
- `tool-web`: 搜索工具注册逻辑从硬绑定 Brave 改为多后端降级；web_fetch 返回 Markdown 而非原始 HTML；增加工具可用性前置检查

## Impact

- **代码**：`src/open_agent/tools/web.py`（新增 DuckDuckGo 工具类）、`src/open_agent/registry.py`（注册逻辑改造）、`src/open_agent/agent/react.py`（success 判断改进）
- **依赖**：新增 `duckduckgo-search` Python 包（免费开源）
- **配置**：`ToolsConfig` 新增 `search_backend` 字段（可选 `auto`/`duckduckgo`/`brave`），默认 `auto`
- **向后兼容**：已配置 `brave_search_api_key` 的用户不受影响，`auto` 模式下优先使用 Brave
