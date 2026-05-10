"""Error Classifier — maps errors to ToolErrorType for deterministic strategy selection."""

from __future__ import annotations

from enum import Enum

from open_agent.errors import (
    ParseError,
    ParameterError,
    RetrievalError,
    ServiceError,
    ToolError,
)


class ToolErrorType(str, Enum):
    """Canonical error categories used to select a recovery strategy chain."""

    ParameterError = "parameter_error"
    RetrievalError = "retrieval_error"
    ServiceError = "service_error"
    ParseError = "parse_error"


class ErrorClassifier:
    """Classify a ToolError (or any Exception) into a ToolErrorType.

    Rules (deterministic, no LLM):
    1. If the exception is an instance of a specific ToolError subclass,
       return the matching ToolErrorType directly.
    2. If it is a plain ToolError, inspect its ``tool_name`` / message
       attributes for heuristic matches.
    3. If the exception is not a ToolError at all, fall back to a
       best-effort classification based on common patterns, or default
       to ServiceError as the safest generic bucket.
    """

    # Simple substring heuristics used when the error is a bare ToolError.
    _HEURISTICS: dict[ToolErrorType, list[str]] = {
        ToolErrorType.ParameterError: [
            "parameter",
            "argument",
            "missing",
            "type error",
            "validation",
        ],
        ToolErrorType.RetrievalError: [
            "not found",
            "no results",
            "empty result",
            "retrieval",
            "query returned",
        ],
        ToolErrorType.ServiceError: [
            "timeout",
            "unavailable",
            "connection",
            "503",
            "502",
            "500",
            "rate limit",
        ],
        ToolErrorType.ParseError: [
            "parse",
            "json",
            "format",
            "decode",
            "unexpected token",
        ],
    }

    def classify(self, error: Exception) -> ToolErrorType:
        """Return the ToolErrorType for *error*.

        Parameters
        ----------
        error:
            Any exception.  ``ToolError`` subclasses are classified
            deterministically; other exceptions use heuristic matching
            on the error message string.
        """
        # Direct subclass matches -------------------------------------------
        if isinstance(error, ParameterError):
            return ToolErrorType.ParameterError
        if isinstance(error, RetrievalError):
            return ToolErrorType.RetrievalError
        if isinstance(error, ServiceError):
            return ToolErrorType.ServiceError
        if isinstance(error, ParseError):
            return ToolErrorType.ParseError

        # Heuristic matching for bare ToolError or unknown errors -----------
        message = str(error).lower()
        for error_type, keywords in self._HEURISTICS.items():
            for keyword in keywords:
                if keyword in message:
                    return error_type

        # Default bucket ----------------------------------------------------
        return ToolErrorType.ServiceError
