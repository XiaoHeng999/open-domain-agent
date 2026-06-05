# 添加新工具指南

## 最小实现

继承 `Tool` ABC，实现 4 个抽象成员：

```python
from open_agent.tools.base import Tool
from typing import Any


class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "描述工具的功能"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "输入参数描述",
                }
            },
            "required": ["input"],
        }

    async def execute(self, **kwargs: Any) -> str:
        # 实现工具逻辑，返回字符串结果
        return "result"
```

## 可选属性

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `read_only` | `False` | 无副作用的工具设为 `True` |
| `safety_checks` | `[]` | 需要的安全检查类型：`"command"`, `"url"`, `"path"`, `"config"` |
| `output_schema` | `None` | JSON Schema 用于 OutputValidationMiddleware 验证输出 |

## 安全检查示例

```python
class ExecTool(Tool):
    @property
    def safety_checks(self) -> list[str]:
        return ["command"]  # 触发 CommandSafetyChecker
```

## 输出验证示例

```python
class MyTool(Tool):
    output_schema = {
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    }

    def validate_output(self, result: str) -> list[str]:
        """语义级输出验证。返回错误列表（空 = 通过）。"""
        errors = []
        if "error" in result.lower():
            errors.append("Output contains error markers")
        return errors
```

## 注册工具

在 `src/open_agent/registry.py` 的 `scan_builtin_tools()` 中添加：

```python
from open_agent.tools.my_tool import MyTool

def scan_builtin_tools() -> list[Tool]:
    tools = [
        ReadFileTool(), WriteFileTool(), ...
        MyTool(),  # 添加这里
    ]
    return [t for t in tools]
```

## 工具参数类型转换

`Tool.cast_params()` 自动处理 LLM 输出的常见问题：
- `str → int`：`"42" → 42`
- `str → bool`：`"true" → True`, `"false" → False`
- `null → ""`：`None → ""`（字符串类型字段）

无需手动处理，框架自动根据 JSON Schema 转换。

## 测试要求

每个工具必须有对应的测试文件 `tests/test_tool_my_tool.py`：

```python
import pytest

@pytest.mark.asyncio
async def test_my_tool_basic():
    tool = MyTool()
    result = await tool.execute(input="test")
    assert result  # 非空

def test_my_tool_schema():
    tool = MyTool()
    schema = tool.to_schema()
    assert schema["name"] == "my_tool"
    assert "input_schema" in schema

def test_my_tool_validation():
    tool = MyTool()
    errors = tool.validate_params({})
    assert any("required" in e.lower() for e in errors)
```

## 常见陷阱

- **不要用 `@tool_schema`**：已废弃，使用 Tool ABC 继承
- **返回值必须是 str**：`execute()` 返回字符串，框架处理后续
- **不要绕过安全检查**：即使工具内部执行命令，也要声明 `safety_checks = ["command"]`
- **异步必须用 async def**：同步的 `execute()` 不会被 await
