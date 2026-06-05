# 添加中间件指南

## 中间件管道架构

```
工具调用请求
  → SafetyMiddleware      （安全检查，可阻断）
  → PermissionMiddleware   （权限决策，可阻断）
  → ExecuteMiddleware      （实际执行）
  → OutputValidationMiddleware  （输出验证）
  → TruncateMiddleware     （token 截断）
  → 返回结果
```

- **Safety** 和 **Permission** 是外层，可以短路阻断（返回 blocked 结果）
- **Execute** 是终端中间件，调用工具的 `execute()` 方法
- **OutputValidation** 和 **Truncate** 是后处理层

## Middleware 协议

```python
from typing import Any, Awaitable, Callable

# Middleware 是一个 async 函数签名
Middleware = Callable[..., Awaitable[Any]]
```

中间件接收 `tool`、`params`、`context` 和 `next_middleware` 参数，调用 `next_middleware` 传递到下一层。

## 实现自定义中间件

```python
from typing import Any

async def MyMiddleware(
    tool: Any,
    params: dict[str, Any],
    context: dict[str, Any],
    next_middleware: Any,
) -> dict[str, Any]:
    # 前置逻辑（在工具执行前）
    result = await next_middleware(tool, params, context)

    # 后置逻辑（在工具执行后）
    return result
```

## 注册中间件

在 `src/open_agent/middleware.py` 的 `build_middleware_chain()` 中添加：

```python
def build_middleware_chain(
    safety_manager, permission_guard, ...
) -> Callable:
    middlewares = [
        SafetyMiddleware(safety_manager),
        PermissionMiddleware(permission_guard),
        MyMiddleware,           # 按位置插入
        ExecuteMiddleware(),
        OutputValidationMiddleware(),
        TruncateMiddleware(max_tokens),
    ]
    # 从内到外构建链
    chain = middlewares[-1]
    for mw in reversed(middlewares[:-1]):
        chain = lambda tool, params, ctx, m=mw, n=chain: m(tool, params, ctx, n)
    return chain
```

## 常见中间件模式

### 前置检查（可阻断）

```python
async def RateLimitMiddleware(tool, params, context, next_mw):
    if is_rate_limited(tool.name):
        return {"blocked": True, "reason": "Rate limit exceeded"}
    return await next_mw(tool, params, context)
```

### 后置处理（不可阻断）

```python
async def LoggingMiddleware(tool, params, context, next_mw):
    result = await next_mw(tool, params, context)
    logger.info("Tool %s executed", tool.name)
    return result
```

### 包装/增强

```python
async def RetryMiddleware(tool, params, context, next_mw):
    for attempt in range(3):
        try:
            return await next_mw(tool, params, context)
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.1 * (2 ** attempt))
```

## 注意事项

- **顺序很重要**：安全/权限必须在 Execute 之前
- **不要跳过 next**：除非你要阻断请求，否则必须调用 `next_middleware`
- **保持无状态**：中间件不应保存请求间的状态
- **异常传播**：未捕获的异常会中断整个链
