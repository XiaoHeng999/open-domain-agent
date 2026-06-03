"""Tests for provider hardening: temperature passthrough + retry on transient errors."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent.config import ModelConfig
from open_agent.types import ToolCall, ToolCallResponse


# --- Temperature tests ---

class TestAnthropicTemperature:
    @pytest.mark.asyncio
    async def test_complete_passes_temperature(self):
        """Anthropic complete() passes temperature to API call."""
        from open_agent.model import AnthropicProvider

        config = ModelConfig(provider="anthropic", name="claude-sonnet-4-6", temperature=0.3)
        provider = AnthropicProvider(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hello")]

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        await provider.complete([{"role": "user", "content": "hi"}])

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.3

    @pytest.mark.asyncio
    async def test_complete_with_tools_passes_temperature(self):
        """Anthropic complete_with_tools() passes temperature to API call."""
        from open_agent.model import AnthropicProvider

        config = ModelConfig(provider="anthropic", name="claude-sonnet-4-6", temperature=0.5)
        provider = AnthropicProvider(config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="done")]
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        await provider.complete_with_tools(
            [{"role": "user", "content": "hi"}],
            [{"name": "echo", "description": "echo", "input_schema": {}}],
        )

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.5


# --- Retry tests ---

class _HTTPError(Exception):
    """Mock HTTP error with status_code on response attribute."""
    def __init__(self, status_code: int, message: str = "error"):
        self.message = message
        self.response = MagicMock()
        self.response.status_code = status_code
        super().__init__(message)


class TestRetryOnTransientErrors:
    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """429 response triggers retry and eventually succeeds."""
        from open_agent.model import AnthropicProvider

        config = ModelConfig(provider="anthropic", name="claude-sonnet-4-6")
        provider = AnthropicProvider(config)

        mock_ok = MagicMock()
        mock_ok.content = [MagicMock(text="success")]

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _HTTPError(429, "rate limited")
            return mock_ok

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = mock_create
        provider._client = mock_client

        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_503(self):
        """503 response triggers retry."""
        from open_agent.model import AnthropicProvider

        config = ModelConfig(provider="anthropic", name="claude-sonnet-4-6")
        provider = AnthropicProvider(config)

        mock_ok = MagicMock()
        mock_ok.content = [MagicMock(text="ok")]

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _HTTPError(503, "service unavailable")
            return mock_ok

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = mock_create
        provider._client = mock_client

        result = await provider.complete([{"role": "user", "content": "hi"}])
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_transient_error_not_retried(self):
        """400 errors are not retried."""
        from open_agent.model import AnthropicProvider

        config = ModelConfig(provider="anthropic", name="claude-sonnet-4-6")
        provider = AnthropicProvider(config)

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            raise _HTTPError(400, "bad request")

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = mock_create
        provider._client = mock_client

        with pytest.raises(_HTTPError):
            await provider.complete([{"role": "user", "content": "hi"}])
        assert call_count == 1
