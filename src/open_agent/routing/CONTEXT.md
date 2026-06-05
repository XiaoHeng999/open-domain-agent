# routing/ — 请求路由

- `complexity.py` — ComplexityJudge：rule-based 或 LLM 分类（simple/complex）
- `domain.py` — DomainRouter：关键词匹配 4 个领域（coding/search/web/general）
- `intent.py` — IntentParser：结构化意图 + slot 提取
- `router.py` — RoutingPipeline：3 级管道编排器
- `unified.py` — UnifiedLLMRouter：单次 LLM 调用替代 3 级管道
