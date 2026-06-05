# 测试规范

## 测试约定

- 框架：pytest + pytest-asyncio（`asyncio_mode = auto`）
- 目录：`tests/`，与 `src/open_agent/` 对应
- 命名：`test_<module>.py`，如 `test_tool_filesystem.py`、`test_recovery.py`
- 异步：所有 async 测试函数直接用 `async def`，不需要 `@pytest.mark.asyncio`

## 运行测试

```bash
# 运行全部
pytest tests/ -x -q

# 运行单个文件
pytest tests/test_recovery.py -v

# 运行匹配的测试
pytest tests/ -k "test_safety" -v

# 全部验证（测试 + lint + 类型检查）
make check
```

## 核心 Fixture 模式

### 创建 Mock Provider

```python
from unittest.mock import AsyncMock
from open_agent.model import OpenAIProvider

def make_mock_provider(response_text="done"):
    provider = AsyncMock(spec=OpenAIProvider)
    provider.complete_with_tools.return_value = ToolCallResponse(
        text=response_text,
        tool_calls=[],
        stop_reason="end_turn",
    )
    return provider
```

### 创建 Tool 实例

```python
from open_agent.tools.filesystem import ReadFileTool

def make_read_tool(workspace="/tmp/test_workspace"):
    tool = ReadFileTool()
    tool._workspace_root = workspace
    return tool
```

### 创建 ToolRegistry

```python
from open_agent.registry import ToolRegistry

def make_registry(tools=None):
    registry = ToolRegistry()
    for tool in (tools or []):
        registry.register(tool)
    return registry
```

## 测试分类

### 1. 工具测试

```python
@pytest.mark.asyncio
async def test_read_file_basic(tmp_path):
    # 创建测试文件
    (tmp_path / "test.txt").write_text("hello")

    tool = ReadFileTool()
    tool._workspace_root = str(tmp_path)
    result = await tool.execute(path="test.txt")

    assert "hello" in result
```

### 2. 中间件测试

```python
@pytest.mark.asyncio
async def test_safety_middleware_blocks_dangerous_command():
    safety = SafetyManager(level="strict")
    middleware = SafetyMiddleware(safety)

    mock_tool = AsyncMock()
    mock_tool.name = "exec"
    mock_tool.safety_checks = ["command"]

    result = await middleware(
        tool=mock_tool,
        params={"command": "rm -rf /"},
        context={},
        next_middleware=AsyncMock(),
    )
    assert result["blocked"] is True
```

### 3. 恢复策略测试

```python
@pytest.mark.asyncio
async def test_service_recovery_retry():
    strategy = ServiceRecoveryStrategy()
    error = ServiceError("timeout", tool_name="web_search")

    # 第一次失败，第二次成功
    call_count = 0
    async def mock_handler(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ServiceError("retry")
        return "success"

    result = await strategy.execute(
        error,
        {"tool_handler": mock_handler, "args": {}},
    )
    assert result.status == RecoveryStatus.SUCCESS
```

### 4. 集成测试

```python
@pytest.mark.asyncio
async def test_react_loop_with_tools(tmp_path):
    # 端到端测试：ReAct 循环 + 工具执行 + 中间件
    ...
```

## Mock 策略

- **不 mock 数据结构**：直接构造真实的 `ToolCall`、`Checkpoint` 等
- **不 mock 工具逻辑**：文件系统工具用 `tmp_path`，不 mock `execute()`
- **可以 mock 外部服务**：LLM provider、HTTP 请求、Docker API
- **可以 mock 时间**：`freezegun` 或手动 patch `time.monotonic`

## 现有测试覆盖

43 个测试文件，819 个测试用例，覆盖所有主要子系统。关键测试文件：

| 文件 | 覆盖范围 |
|------|---------|
| `test_agent.py` | Agent 基础功能 |
| `test_react_tool_use.py` | ReAct 循环 + 工具调用 |
| `test_middleware_chain.py` | 中间件管道 |
| `test_security.py` | 安全系统 |
| `test_permission.py` | 权限系统 |
| `test_recovery.py` | 错误恢复 |
| `test_checkpoint.py` | 检查点保存/恢复 |
| `test_routing.py` | 路由管道 |
| `test_e2e.py` | 端到端集成 |
| `test_p0_regression.py` | P0 回归测试 |
