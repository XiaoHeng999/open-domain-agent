"""Model interface and ProviderFactory — config-driven LLM provider creation."""
from __future__ import annotations

import json
import logging
import re
import warnings
from typing import Any

from open_agent.base import ModelProvider
from open_agent.config import ModelConfig
from open_agent.types import ToolCall, ToolCallResponse

# Retry decorator for transient API errors
try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception,
    )

    def _is_transient(exc: BaseException) -> bool:
        """Return True for transient HTTP errors that should be retried."""
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (429, 502, 503):
            return True
        # Connection errors (timeouts, network failures)
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return True
        # httpx transport errors
        if type(exc).__name__ in ("ConnectError", "ReadTimeout", "PoolTimeout"):
            return True
        return False

    _api_retry = retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
except ImportError:
    # tenacity not installed — no retry
    def _api_retry(fn):
        return fn

logger = logging.getLogger("open_agent")


class ProviderFactory:
    """Create LLM provider instances from config."""

    _registry: dict[str, type[ModelProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[ModelProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, config: ModelConfig) -> ModelProvider:
        provider_name = config.provider
        if provider_name not in cls._registry:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {list(cls._registry.keys())}"
            )
        return cls._registry[provider_name](config)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._registry.keys())


class OpenAIProvider(ModelProvider):
    """OpenAI-compatible provider (also used for DeepSeek)."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._client = None

    async def on_start(self) -> None:
        try:
            from openai import AsyncOpenAI

            kwargs: dict[str, Any] = {}
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = AsyncOpenAI(**kwargs)
        except ImportError:
            raise ImportError("Install openai: pip install openai")

    @_api_retry
    async def _openai_create(self, **kwargs: Any) -> Any:
        """Raw OpenAI API call with retry on transient errors."""
        return await self._client.chat.completions.create(**kwargs)

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        response = await self._openai_create(
            model=self.config.name,
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        return response.choices[0].message.content or ""

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        warnings.warn(
            "complete_structured is deprecated, use complete_with_tools instead",
            DeprecationWarning,
            stacklevel=2,
        )
        response = await self._openai_create(
            model=self.config.name,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)
        text = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for start_ch, end_ch in [("{", "}"), ("[", "]")]:
                start = text.find(start_ch)
                if start != -1:
                    end = text.rfind(end_ch)
                    if end > start:
                        try:
                            return json.loads(text[start : end + 1])
                        except json.JSONDecodeError:
                            continue
            raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ToolCallResponse:
        """Call OpenAI API with function-calling tools."""
        stream = kwargs.pop("stream", False)
        on_chunk = kwargs.pop("on_chunk", None)
        openai_tools = _anthropic_to_openai_tools(tool_definitions)

        api_kwargs = {
            "model": self.config.name,
            "messages": messages,
            "tools": openai_tools,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        if stream and on_chunk:
            return await self._stream_openai(api_kwargs, on_chunk)

        response = await self._openai_create(**api_kwargs)

        choice = response.choices[0]
        message = choice.message
        text = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                ))

        stop_reason = "tool_use" if tool_calls else "end_turn"

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens or 0,
                "output_tokens": response.usage.completion_tokens or 0,
            }

        return ToolCallResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw_response=response,
            usage=usage,
        )

    async def _stream_openai(
        self,
        api_kwargs: dict[str, Any],
        on_chunk,
    ) -> ToolCallResponse:
        """Stream OpenAI API response, calling on_chunk for each text delta."""
        api_kwargs["stream"] = True
        chunks = await self._openai_create(**api_kwargs)

        text_parts: list[str] = []
        usage_data = None

        async for chunk in chunks:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                text_parts.append(delta.content)
                if on_chunk:
                    result = on_chunk(delta.content)
                    if hasattr(result, "__await__"):
                        await result
            # Check for usage in final chunk
            if hasattr(chunk, "usage") and chunk.usage:
                usage_data = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

        return ToolCallResponse(
            text="".join(text_parts),
            tool_calls=[],
            stop_reason="end_turn",
            raw_response=None,
            usage=usage_data,
        )


class AnthropicProvider(ModelProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._client = None

    async def on_start(self) -> None:
        try:
            from anthropic import AsyncAnthropic

            kwargs: dict[str, Any] = {}
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            self._client = AsyncAnthropic(**kwargs)
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

    @_api_retry
    async def _anthropic_create(self, **kwargs: Any) -> Any:
        """Raw Anthropic API call with retry on transient errors."""
        return await self._client.messages.create(**kwargs)

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        system = None
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        response = await self._anthropic_create(
            model=self.config.name,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system=system or "",
            messages=user_messages,
        )
        return response.content[0].text if response.content else ""

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        warnings.warn(
            "complete_structured is deprecated, use complete_with_tools instead",
            DeprecationWarning,
            stacklevel=2,
        )
        text = await self.complete(
            messages + [{"role": "user", "content": "Respond in valid JSON."}],
            **kwargs,
        )
        return json.loads(text)

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ToolCallResponse:
        """Call Anthropic API with native tool_use support."""
        stream = kwargs.pop("stream", False)
        on_chunk = kwargs.pop("on_chunk", None)
        system = None
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        # Apply prompt caching markers when enabled
        api_tools = list(tool_definitions)
        api_system = system or ""
        if self.config.caching:
            # System message as list with cache_control on the last block
            if api_system:
                api_system = [
                    {"type": "text", "text": api_system, "cache_control": {"type": "ephemeral"}},
                ]
            # Add cache_control to the last tool definition
            if api_tools:
                cached_tools = [dict(t) for t in api_tools]
                cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}
                api_tools = cached_tools

        api_kwargs = {
            "model": self.config.name,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "system": api_system,
            "messages": user_messages,
            "tools": api_tools,
        }

        if stream and on_chunk:
            return await self._stream_anthropic(api_kwargs, on_chunk)

        response = await self._anthropic_create(**api_kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens or 0,
                "output_tokens": response.usage.output_tokens or 0,
            }

        return ToolCallResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
            raw_response=response,
            usage=usage,
        )

    async def _stream_anthropic(
        self,
        api_kwargs: dict[str, Any],
        on_chunk,
    ) -> ToolCallResponse:
        """Stream Anthropic API response, calling on_chunk for each text delta."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        stop_reason = "end_turn"
        usage_data = None

        async with self._client.messages.stream(**api_kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text") and delta.text:
                        text_parts.append(delta.text)
                        if on_chunk:
                            result = on_chunk(delta.text)
                            if hasattr(result, "__await__"):
                                await result
                elif event.type == "message_start":
                    msg = event.message
                    if hasattr(msg, "usage") and msg.usage:
                        usage_data = {
                            "input_tokens": msg.usage.input_tokens or 0,
                            "output_tokens": 0,
                        }
                elif event.type == "message_delta":
                    delta = event.delta
                    if hasattr(delta, "stop_reason") and delta.stop_reason:
                        stop_reason = delta.stop_reason
                    usage_event = event.usage if hasattr(event, "usage") else None
                    if usage_event and usage_data is not None:
                        usage_data["output_tokens"] = usage_event.output_tokens or 0

            # Get final message for tool calls
            final_message = await stream.get_final_message()
            for block in final_message.content:
                if block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    ))
            if not usage_data and hasattr(final_message, "usage") and final_message.usage:
                usage_data = {
                    "input_tokens": final_message.usage.input_tokens or 0,
                    "output_tokens": final_message.usage.output_tokens or 0,
                }

        return ToolCallResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw_response=None,
            usage=usage_data,
        )


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek provider — uses OpenAI-compatible API."""

    def __init__(self, config: ModelConfig) -> None:
        if not config.base_url:
            config = config.model_copy(update={"base_url": "https://api.deepseek.com"})
        super().__init__(config)


class LocalProvider(ModelProvider):
    """Stub for local model provider."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        return "Local model response (stub)"

    async def complete_structured(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        warnings.warn(
            "complete_structured is deprecated, use complete_with_tools instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return {"result": "stub"}


def _anthropic_to_openai_tools(
    anthropic_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Anthropic tool_use format to OpenAI function-calling format."""
    openai_tools = []
    for t in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return openai_tools


# Register built-in providers
ProviderFactory.register("openai", OpenAIProvider)
ProviderFactory.register("anthropic", AnthropicProvider)
ProviderFactory.register("deepseek", DeepSeekProvider)
ProviderFactory.register("local", LocalProvider)
