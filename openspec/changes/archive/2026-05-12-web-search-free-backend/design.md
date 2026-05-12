## Context

当前 `WebSearchTool` 硬绑定 Brave Search API（`web.py:57`），需要付费 API Key 才能工作。未配置 Key 时工具仍被注册到 Registry，LLM 会选中它并反复重试失败。`WebFetchTool` 返回原始 HTML 响应体，LLM 需要自行从 HTML 中提取信息，效率低下且浪费 token。

参考 Claude Code 的做法：
- **WebSearch**：使用 Anthropic server-side tool，不支持时直接隐藏工具
- **WebFetch**：HTML → Markdown 转换 → 用小模型做内容摘要

我们无法使用 Anthropic server-side tool（因为用的是 OpenAI 兼容 API），因此需要自建搜索能力。行业方案对比后选择 DuckDuckGo（通过 `duckduckgo-search` 库）作为免费默认后端。

## Goals / Non-Goals

**Goals:**
- 默认配置下（零 API Key）搜索能力开箱即用
- 多后端支持：DuckDuckGo（免费默认）+ Brave Search（付费可选）
- 不可用工具不注册到 Registry（学 Claude Code）
- `web_fetch` 返回 Markdown 格式，提升 LLM 可读性
- `success` 判断不再依赖字符串前缀匹配

**Non-Goals:**
- 不做 SearXNG 自托管集成（需要额外部署）
- 不做 Tavily 集成（付费服务）
- 不做 Claude Code 风格的"用小模型摘要 web_fetch 内容"（当前阶段过度设计）
- 不改 Anthropic server-side tool（我们用 OpenAI 兼容 API）

## Decisions

### 决策 1：搜索后端选择 DuckDuckGo

**选择**：`duckduckgo-search` Python 库
**替代方案**：
- Brave Search API：付费，需 API Key → 作为可选后端保留
- SearXNG：需自托管部署 → 太重
- Tavily：专为 AI Agent 设计但付费 → 不作默认
- 直接 HTTP 抓取搜索引擎：不稳定、易被封

**理由**：DuckDuckGo 通过 `duckduckgo-search` 库提供免费、无需 Key、稳定的搜索接口，一行代码即可使用。在 `auto` 模式下作为 Brave 的降级兜底。

### 决策 2：后端选择策略 — 优先级降级 + 条件注册

**策略**：
```
search_backend = "auto"（默认）
  → 有 brave_search_api_key → 注册 BraveSearchTool
  → 否则 → 注册 DuckDuckGoSearchTool

search_backend = "duckduckgo"
  → 注册 DuckDuckGoSearchTool

search_backend = "brave"
  → 有 brave_search_api_key → 注册 BraveSearchTool
  → 否则 → 不注册搜索工具（LLM 看不到）

所有搜索工具统一使用 name="web_search"，外部接口不变
```

**理由**：LLM 看到的工具名始终是 `web_search`，不关心后端是谁。注册逻辑保证 LLM 只看到可用的工具，消除无效重试。

### 决策 3：web_fetch 返回 Markdown

**选择**：用 `markdownify` 库将 HTML 转 Markdown
**替代方案**：
- 返回原始 HTML：LLM 不擅长解析 HTML
- 正则提取文本：丢失结构信息
- Turndown.js：Claude Code 用的，但我们是 Python 项目

**理由**：Markdown 保留文档结构（标题、列表、链接），LLM 天然擅长阅读 Markdown，且比 HTML 紧凑得多，节省 token。

### 决策 4：success 判断改为检查中间件链返回结果

**选择**：`success = not content.startswith("Error:")` 保持不变，但在 `ToolRegistry.execute()` 层面确保永远返回字符串
**理由**：这是最小改动。中间件链的所有路径（Safety/Permission/Execute）已经保证返回字符串。真正的 risk 在于 `str(result)` 对 dict 的处理，加一个类型断言即可。

## Risks / Trade-offs

- **[DuckDuckGo 速率限制]** → DuckDuckGo 非官方 API，高频请求可能被限流。缓解：库内置重试机制，加配置项 `search_rate_limit`
- **[duckduckgo-search 库维护风险]** → 该库是第三方开源项目。缓解：抽象出统一的搜索接口，后端可替换
- **[markdownify 额外依赖]** → 新增一个轻量依赖。缓解：仅在 web_fetch 实际执行时 import，不影响其他模块
- **[BREAKING: WebSearchTool 重命名]** → 外部代码如直接引用 `WebSearchTool` 需改为 `BraveSearchTool`。缓解：在 `web.py` 保留 `WebSearchTool = BraveSearchTool` 别名
