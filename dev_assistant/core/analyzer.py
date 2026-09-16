"""Validate a snippet, get it analyzed, hand back the result.

It talks to the provider only through the
:class:`~dev_assistant.core.llm_client.StructuredLLMClient` protocol, so tests
substitute a fake client with no network.
"""

from __future__ import annotations

from dataclasses import dataclass

from dev_assistant.config import Settings
from dev_assistant.core.errors import InputValidationError
from dev_assistant.core.llm_client import StructuredLLMClient, build_client
from dev_assistant.core.prompts import (
    SYSTEM_PROMPT,
    CodeAnalysis,
    build_user_prompt,
)


@dataclass(frozen=True)
class AnalysisRequest:
    """One unit of work: a snippet plus whatever context we have about it."""

    code: str
    language: str | None = None
    filename: str | None = None
    focus: str | None = None


class CodeAnalyzer:
    """Turns an :class:`AnalysisRequest` into a validated :class:`CodeAnalysis`."""

    def __init__(
        self,
        client: StructuredLLMClient,
        *,
        max_snippet_chars: int = 100_000,
    ) -> None:
        self._client = client
        self._max_snippet_chars = max_snippet_chars

    def analyze(self, request: AnalysisRequest) -> CodeAnalysis:
        """Analyze one snippet.

        Args:
            request: The snippet and its context. ``request.code`` is treated
                strictly as text and is never executed.

        Returns:
            A fully validated analysis.

        Raises:
            InputValidationError: The snippet is empty or too large. Checked
                locally so an unusable request never costs an API call.
            LLMError: Any failure reaching or parsing the provider's response.
        """
        code = self._validate(request.code)

        prompt = build_user_prompt(
            code,
            language=request.language,
            filename=request.filename,
            focus=request.focus,
        )

        return self._client.generate_structured(
            system_instruction=SYSTEM_PROMPT,
            prompt=prompt,
            schema=CodeAnalysis,
        )

    def _validate(self, code: str) -> str:
        """Reject snippets that cannot produce a useful analysis."""
        if not code.strip():
            raise InputValidationError(
                "The snippet is empty. Pass a file path, or pipe code in on stdin."
            )

        if len(code) > self._max_snippet_chars:
            raise InputValidationError(
                f"The snippet is {len(code):,} characters, over the "
                f"{self._max_snippet_chars:,} limit. Analyze a single module or "
                "function at a time, or raise MAX_SNIPPET_CHARS in your .env."
            )

        return code


def build_analyzer(settings: Settings) -> CodeAnalyzer:
    """Connect an analyzer to the configured provider."""
    return CodeAnalyzer(
        build_client(settings),
        max_snippet_chars=settings.max_snippet_chars,
    )
