"""Unified error type hierarchy for the agent framework."""

from __future__ import annotations


class AgentError(Exception):
    """Base error for all agent framework errors."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.cause:
            return f"{base} (caused by: {self.cause})"
        return base


class ToolError(AgentError):
    """Error during tool execution."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.tool_name = tool_name


class ParameterError(ToolError):
    """Tool parameter format/type/missing error."""


class RetrievalError(ToolError):
    """Tool retrieval result error."""


class ServiceError(ToolError):
    """External service unavailable or timeout error."""


class ParseError(ToolError):
    """Tool output parsing error."""


class MemoryError(AgentError):
    """Memory operation error."""

    def __init__(
        self,
        message: str,
        memory_layer: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.memory_layer = memory_layer


class RoutingError(AgentError):
    """Routing decision error."""


class EvalError(AgentError):
    """Evaluation pipeline error."""


class DangerousOperationError(AgentError):
    """Raised when a dangerous operation is blocked."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.reason = reason


class SSRFError(AgentError):
    """Raised when an SSRF attempt is blocked."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.reason = reason


class SecurityError(AgentError):
    """General security violation."""

    def __init__(
        self,
        message: str,
        check_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.check_type = check_type
