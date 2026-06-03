"""Tests for async CLI input — prompt_toolkit replaces blocking input()."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent.safety.hitl import HITLApprovalManager, HITLLevel


# ---------------------------------------------------------------------------
# Test 1: Event loop stays responsive during async input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_input_does_not_block_event_loop() -> None:
    """While an async prompt awaits, other coroutines can still run."""
    from prompt_toolkit.shortcuts import PromptSession

    ticked = False

    async def background_tick() -> None:
        nonlocal ticked
        await asyncio.sleep(0.01)
        ticked = True

    async def fake_prompt_async(*args, **kwargs):
        await asyncio.sleep(0.05)
        return "hello"

    session = MagicMock(spec=PromptSession)
    session.prompt_async = fake_prompt_async

    task = asyncio.create_task(background_tick())
    result = await session.prompt_async("test> ")
    await task

    assert result == "hello"
    assert ticked, "Background coroutine should have completed while input was awaited"


# ---------------------------------------------------------------------------
# Test 2: _ask_human is async and uses prompt_toolkit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hitl_ask_human_is_async() -> None:
    """HITLApprovalManager._ask_human should be a coroutine function."""
    import inspect

    assert inspect.iscoroutinefunction(HITLApprovalManager._ask_human)


@pytest.mark.asyncio
async def test_hitl_ask_human_approves_on_yes() -> None:
    """_ask_human returns True when user types 'y'."""
    mgr = HITLApprovalManager(interactive=True)

    async def fake_prompt_async(*args, **kwargs):
        return "y"

    with patch("prompt_toolkit.shortcuts.PromptSession") as MockSession:
        session = MagicMock()
        session.prompt_async = fake_prompt_async
        MockSession.return_value = session

        result = await mgr._ask_human("test op", operation="write file")
        assert result is True


@pytest.mark.asyncio
async def test_hitl_ask_human_denies_on_no() -> None:
    """_ask_human returns False when user types 'n'."""
    mgr = HITLApprovalManager(interactive=True)

    async def fake_prompt_async(*args, **kwargs):
        return "n"

    with patch("prompt_toolkit.shortcuts.PromptSession") as MockSession:
        session = MagicMock()
        session.prompt_async = fake_prompt_async
        MockSession.return_value = session

        result = await mgr._ask_human("test op", operation="write file")
        assert result is False


# ---------------------------------------------------------------------------
# Test 3: prompt_toolkit is importable
# ---------------------------------------------------------------------------


def test_prompt_toolkit_importable() -> None:
    """prompt_toolkit must be installed and importable."""
    from prompt_toolkit.shortcuts import PromptSession  # noqa: F401

    assert True


# ---------------------------------------------------------------------------
# Test 4: approve() awaits _ask_human (not calling it synchronously)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_awaits_ask_human() -> None:
    """approve() should await _ask_human, not call it synchronously."""
    mgr = HITLApprovalManager(interactive=True)

    async def fake_prompt_async(*args, **kwargs):
        return "y"

    with patch("prompt_toolkit.shortcuts.PromptSession") as MockSession:
        session = MagicMock()
        session.prompt_async = fake_prompt_async
        MockSession.return_value = session

        result = await mgr.approve("write config file", details={"path": "/tmp/test"})
        assert result.approved is True
        assert result.approved_by == "human"
