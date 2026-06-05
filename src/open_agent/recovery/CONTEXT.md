# recovery/ — 错误恢复

- `classifier.py` — ErrorClassifier：异常 → ToolErrorType（Parameter/Retrieval/Service/Parse）
- `engine.py` — RecoveryChain（策略链）+ RecoveryPolicyRegistry（自定义策略注册）
- `strategies.py` — 4 种内置策略：Parameter（修复参数）、Retrieval（扩展查询）、Service（退避重试）、Parse（格式切换）
