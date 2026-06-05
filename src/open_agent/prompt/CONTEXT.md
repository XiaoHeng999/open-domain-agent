# prompt/ — 系统提示组装

- `builder.py` — PromptBuilder：6 段有序组装，token 预算截断，稳定段缓存
- `segments.py` — 6 个 Segment 实现：CoreIdentity / ToolList / Skills / Memory / CLAUDEMD / DynamicEnv
- `prompt.py` — 提示模板常量和分隔符
