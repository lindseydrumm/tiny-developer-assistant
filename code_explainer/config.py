"""Configuration, sourced strictly from the environment.

CONSTITUTION.md II.1: no key, secret, or credential may appear in source code,
default arguments, or tests. ``gemini_api_key`` below has no default -- if the
environment does not supply it, construction fails loudly.
"""

from __future__ import annotations

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from code_explainer.core.errors import ConfigurationError


class Settings(BaseSettings):
    """Runtime configuration read from the environment or a local ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str = Field(
        min_length=1,
        description="Google AI Studio API key. Required; never has a default.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Model id. Flash is the free-tier workhorse.",
    )
    request_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Per-request timeout in seconds.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Retry attempts for throttling and server-side failures.",
    )
    max_snippet_chars: int = Field(
        default=100_000,
        gt=0,
        description="Reject snippets larger than this before spending a request.",
    )


def load_settings(**overrides: object) -> Settings:
    """Build :class:`Settings`, translating validation noise into guidance.

    ``**overrides`` lets the interface layer apply command-line flags on top of
    the environment without reaching into pydantic internals.
    """
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise ConfigurationError(_describe(exc)) from exc


def _describe(exc: ValidationError) -> str:
    """Turn a pydantic ValidationError into setup instructions."""
    missing_key = any(
        error["loc"] == ("gemini_api_key",) and error["type"] == "missing"
        for error in exc.errors()
    )
    if missing_key:
        return (
            "GEMINI_API_KEY is not set.\n"
            "  1. Get a free key at https://aistudio.google.com/apikey\n"
            "  2. cp .env.example .env\n"
            "  3. Paste the key into .env (it is git-ignored), or export "
            "GEMINI_API_KEY in your shell."
        )

    problems = "\n".join(
        f"  - {'.'.join(str(part) for part in error['loc']) or 'config'}: {error['msg']}"
        for error in exc.errors()
    )
    return f"Invalid configuration:\n{problems}"
