"""Builders shared across test modules.

Tests construct real ``google.genai`` response objects rather than mocks, so
the parsing tests exercise the same object shape the SDK actually returns.
No test contacts the network and no test contains a credential
(CONSTITUTION.md II.1).
"""

from __future__ import annotations

from typing import Optional

from google.genai import types

#: Not a credential -- a placeholder that satisfies the non-empty check on
#: Settings.gemini_api_key. Nothing in the test suite makes a real request.
PLACEHOLDER_KEY = "placeholder-not-a-real-key"


def make_response(
    *,
    text: Optional[str] = None,
    parsed: object = None,
    finish_reason: types.FinishReason = types.FinishReason.STOP,
    block_reason: Optional[types.BlockedReason] = None,
    with_candidate: bool = True,
) -> types.GenerateContentResponse:
    """Build a provider response.

    ``text`` becomes the candidate's text part (``response.text`` is a derived
    property). ``parsed`` is set directly, mirroring how the SDK populates it
    when ``response_schema`` is supplied.
    """
    candidates = None
    if with_candidate:
        parts = [types.Part(text=text)] if text is not None else None
        candidates = [
            types.Candidate(
                content=types.Content(parts=parts, role="model"),
                finish_reason=finish_reason,
            )
        ]

    prompt_feedback = (
        types.GenerateContentResponsePromptFeedback(block_reason=block_reason)
        if block_reason
        else None
    )

    return types.GenerateContentResponse(
        candidates=candidates,
        prompt_feedback=prompt_feedback,
        parsed=parsed,
    )


def analysis_payload() -> dict:
    """A minimal dict that validates against :class:`CodeAnalysis`."""
    return {
        "language": "Python",
        "summary": "Adds two numbers.",
        "key_points": ["Performs no validation."],
        "blocks": [
            {
                "lines": "1-2",
                "heading": "Addition helper",
                "explanation": "Returns the sum of its two arguments.",
            }
        ],
        "refactorings": [
            {
                "title": "Add type hints",
                "severity": "low",
                "lines": "1",
                "rationale": "The signature is untyped.",
                "suggestion": "def add(a: int, b: int) -> int:",
            }
        ],
    }
