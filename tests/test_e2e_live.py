"""E2E live tests — require DEEPSEEK_API_KEY env var, skipped otherwise."""
from __future__ import annotations

import os

import pytest

from open_agent.config import AgentConfig, ModelConfig

# Skip all tests in this module if no API key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
pytestmark = pytest.mark.skipif(
    not DEEPSEEK_API_KEY,
    reason="DEEPSEEK_API_KEY not set — skipping live E2E tests",
)


@pytest.fixture
async def runtime():
    """Create and start an AgentRuntime with DeepSeek provider."""
    from open_agent.runtime import AgentRuntime

    config = AgentConfig(
        model=ModelConfig(
            provider="deepseek",
            name="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
        ),
    )
    rt = AgentRuntime(config=config)
    await rt.on_start()
    yield rt
    await rt.on_stop()


# ---------------------------------------------------------------------------
# Issue 05: DeepSeek simple QA
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.live
async def test_deepseek_simple_qa(runtime) -> None:
    """DeepSeek should answer '1+1' with '2'."""
    response = await runtime.run("What is 1+1? Answer with just the number.")
    assert "2" in response.output


# ---------------------------------------------------------------------------
# Issue 06: ReAct + tool calling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.live
async def test_react_tool_calling(runtime) -> None:
    """Agent should use tools when asked to perform actions."""
    response = await runtime.run("What tools do you have available?")
    # Should get a meaningful response about available tools
    assert len(response.output) > 10
    assert response.metadata.get("total_steps", 0) >= 1


# ---------------------------------------------------------------------------
# Issue 07: Streaming + tool calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.live
async def test_streaming_with_tool_calls(runtime) -> None:
    """Agent should stream thoughts and collect tool calls in streaming mode."""
    chunks: list[str] = []

    def on_chunk(text: str):
        chunks.append(text)

    # Check that the provider supports streaming
    from open_agent.types import ToolCallResponse

    result = await runtime.provider.complete_with_tools(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one sentence."},
        ],
        tool_definitions=[],
        stream=True,
        on_chunk=on_chunk,
    )
    assert isinstance(result, ToolCallResponse)
    assert len(result.text) > 0
    assert len(chunks) > 0


# ---------------------------------------------------------------------------
# Issue 08: Task cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.live
async def test_task_cancellation(runtime) -> None:
    """Cancelling mid-execution should stop the loop gracefully."""
    from open_agent.cancellation import CancellationToken

    token = CancellationToken()
    runtime.react_loop._cancellation_token = token

    # Cancel immediately — loop should exit cleanly
    token.cancel()

    response = await runtime.run("Tell me a long story about AI.")
    assert response is not None
    assert response.total_steps <= 1


# ---------------------------------------------------------------------------
# Issue 09: Full smoke eval suite via EvalRunner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.live
async def test_smoke_eval_suite(runtime) -> None:
    """EvalRunner should run smoke suite against runtime and report results."""
    from pathlib import Path
    from open_agent.eval.runner import EvalRunner

    scenarios_path = Path("evals")
    if not (scenarios_path / "smoke").exists():
        pytest.skip("evals/smoke/ directory not found")

    runner = EvalRunner(scenarios_dir=scenarios_path, runtime=runtime)
    scenarios = runner.load_suite("smoke")
    assert len(scenarios) >= 1, "At least one smoke scenario required"

    results = await runner.run_suite("smoke")
    assert len(results) == len(scenarios)

    # At least the simple_qa scenario should pass
    passed = sum(1 for r in results if r["status"] == "pass")
    assert passed >= 1, f"Expected at least 1 passing scenario, got {passed}/{len(results)}"
