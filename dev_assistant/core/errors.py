"""Exception hierarchy shared by the core layer.

Every failure the user can plausibly cause or recover from gets its own type
with a human-readable message. The interface layer renders ``str(exc)``
directly, so messages must be actionable on their own (no stack retraces).
"""

from __future__ import annotations


class CodeExplainerError(Exception):
    """Base class for every error this application raises deliberately."""

    #: Suggested process exit code. Subclasses may override.
    exit_code: int = 1


class ConfigurationError(CodeExplainerError):
    """The application is not set up correctly (missing or malformed env vars)."""

    exit_code = 78  # EX_CONFIG


class InputValidationError(CodeExplainerError):
    """The snippet the user supplied cannot be analyzed as-is."""

    exit_code = 64  # EX_USAGE


class LLMError(CodeExplainerError):
    """Base class for anything that went wrong talking to the provider."""

    exit_code = 69  # EX_UNAVAILABLE


class AuthenticationError(LLMError):
    """The API key was rejected."""

    exit_code = 77  # EX_NOPERM


class RateLimitError(LLMError):
    """The provider throttled us and retries did not clear it."""

    exit_code = 75  # EX_TEMPFAIL


class TimeoutError_(LLMError):
    """The request exceeded the configured timeout.

    Named with a trailing underscore so it never shadows the builtin
    ``TimeoutError`` at an import site.
    """

    exit_code = 75  # EX_TEMPFAIL


class ServiceError(LLMError):
    """The provider returned a server-side failure that retries did not clear."""

    exit_code = 69  # EX_UNAVAILABLE


class ResponseValidationError(LLMError):
    """The provider replied, but not with data matching our schema so that 
    raw, unvalidated model text never reaches core logic."""

    exit_code = 65  # EX_DATAERR
