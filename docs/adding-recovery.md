# 添加恢复策略指南

## 恢复系统架构

```
ToolError
  → ErrorClassifier（分类为 Parameter/Retrieval/Service/Parse）
    → RecoveryChain（有序策略链）
      → Strategy 1 → 失败 → Strategy 2 → ... → 全失败则升级(escalate)
```

## 实现恢复策略

继承 `RecoveryStrategy`，实现 `execute()` 方法：

```python
from open_agent.recovery.strategies import (
    RecoveryStrategy,
    RecoveryResult,
    RecoveryStatus,
)
from open_agent.errors import ToolError
from typing import Any


class MyRecoveryStrategy(RecoveryStrategy):
    @property
    def name(self) -> str:
        return "my_recovery"

    async def execute(
        self,
        error: ToolError,
        context: dict[str, Any],
    ) -> RecoveryResult:
        # 尝试恢复逻辑
        tool_handler = context.get("tool_handler")
        args = context.get("args", {})

        try:
            # 修复 args 或使用替代方案
            fixed_args = self._fix_args(args, error)
            if tool_handler and fixed_args:
                result = await tool_handler(**fixed_args)
                return RecoveryResult(
                    status=RecoveryStatus.SUCCESS,
                    recovered_result=str(result),
                    strategy_name=self.name,
                )
        except Exception:
            pass

        return RecoveryResult(
            status=RecoveryStatus.FAILURE,
            strategy_name=self.name,
        )

    def _fix_args(self, args: dict, error: ToolError) -> dict | None:
        # 具体的修复逻辑
        return None
```

## 注册策略

两种方式：

### 1. 添加到默认链

在 `src/open_agent/recovery/engine.py` 的 `DEFAULT_CHAINS` 中添加：

```python
DEFAULT_CHAINS: dict[ToolErrorType, list[RecoveryStrategy]] = {
    ToolErrorType.ServiceError: [
        MyRecoveryStrategy(),  # 添加到链的前面
        ServiceRecoveryStrategy(),
    ],
    ...
}
```

### 2. 运行时注册（优先级更高）

```python
from open_agent.recovery.engine import RecoveryPolicyRegistry
from open_agent.recovery.classifier import ToolErrorType

registry = RecoveryPolicyRegistry()
registry.register(ToolErrorType.ServiceError, MyRecoveryStrategy())
```

运行时注册的策略会插入到默认链前面（优先执行）。

## 内置策略参考

| 策略 | 目标错误 | 恢复方式 |
|------|---------|---------|
| `ParameterRecoveryStrategy` | ParameterError | 合并 fixed_args + 填充 schema 默认值 |
| `RetrievalRecoveryStrategy` | RetrievalError | 扩展查询 → 放宽过滤 → 使用缓存（3 子步） |
| `ServiceRecoveryStrategy` | ServiceError | 指数退避重试（0.1s, 0.2s, 0.4s）→ fallback 工具 |
| `ParseRecoveryStrategy` | ParseError | 尝试替代格式（json/text/csv）→ LLM 辅助修复 |

## 添加新的错误类型

如果需要新的错误类别：

1. 在 `errors.py` 中添加新的错误类（继承 `ToolError`）
2. 在 `recovery/classifier.py` 的 `ToolErrorType` 枚举中添加成员
3. 在 `classifier.py` 的 `_classify_tool_error()` 中添加匹配规则
4. 在 `engine.py` 的 `DEFAULT_CHAINS` 中注册策略链
5. 编写对应的测试

## 测试要求

```python
import pytest
from open_agent.recovery.strategies import RecoveryStatus

@pytest.mark.asyncio
async def test_my_recovery_success():
    strategy = MyRecoveryStrategy()
    error = ServiceError("connection timeout")
    result = await strategy.execute(error, {"tool_handler": mock_handler})
    assert result.status == RecoveryStatus.SUCCESS

@pytest.mark.asyncio
async def test_my_recovery_failure():
    strategy = MyRecoveryStrategy()
    result = await strategy.execute(ServiceError("fatal"), {})
    assert result.status == RecoveryStatus.FAILURE
```
