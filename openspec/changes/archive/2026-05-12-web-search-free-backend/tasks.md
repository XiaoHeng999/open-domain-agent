## 1. 依赖安装

- [x] 1.1 在项目依赖中添加 `duckduckgo-search` 和 `markdownify` 包
- [x] 1.2 验证依赖安装成功，确认 `from duckduckgo_search import DDGS` 和 `import markdownify` 可正常导入

## 2. DuckDuckGo 搜索工具实现

- [x] 2.1 在 `src/open_agent/tools/web.py` 中新增 `DuckDuckGoSearchTool` 类，实现 Tool ABC 接口（name="web_search"，与 Brave 版本统一 schema）
- [x] 2.2 实现 `execute` 方法：使用 `DDGS().text()` 执行搜索，格式化结果为 "序号. 标题\n   URL: ...\n   摘要" 格式
- [x] 2.3 处理边界情况：无结果、网络异常、参数校验

## 3. Brave Search 工具重命名

- [x] 3.1 将 `WebSearchTool` 重命名为 `BraveSearchTool`，更新类名和 docstring
- [x] 3.2 在 `web.py` 末尾添加 `WebSearchTool = BraveSearchTool` 别名保持向后兼容

## 4. WebFetch Markdown 转换

- [x] 4.1 在 `WebFetchTool.execute()` 中引入 `markdownify`，HTML 响应体转换为 Markdown
- [x] 4.2 添加 Content-Type 检测：非 HTML 内容（JSON/纯文本）直接返回原文不做转换
- [x] 4.3 更新截断逻辑确保在 Markdown 转换后执行

## 5. 多后端注册逻辑

- [x] 5.1 在 `ToolsConfig` 中新增 `search_backend: str = "auto"` 字段（可选值：auto/duckduckgo/brave）
- [x] 5.2 重构 `scan_builtin_tools()` 搜索工具注册部分，按 design.md 中的优先级降级策略实现条件注册
- [x] 5.3 `auto` 模式：有 Brave Key → 注册 BraveSearchTool；否则 → 注册 DuckDuckGoSearchTool
- [x] 5.4 `brave` 模式但无 Key → 不注册任何搜索工具（LLM 看不到 web_search）

## 6. 测试验证

- [x] 6.1 为 `DuckDuckGoSearchTool` 编写单元测试（mock DDGS 返回）
- [x] 6.2 为多后端注册逻辑编写测试（覆盖 auto/duckduckgo/brave 三种模式）
- [x] 6.3 为 WebFetch Markdown 转换编写测试
- [x] 6.4 端到端验证：启动 Agent，发送搜索请求，确认搜索成功返回结果
