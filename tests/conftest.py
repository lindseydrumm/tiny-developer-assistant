"""Fixtures available to every test module.

Builders live in :mod:`tests.helpers` so they can be imported explicitly
without loading this module twice (pytest already imports conftest itself).
"""

from __future__ import annotations

import pytest

from code_explainer.core.prompts import CodeAnalysis, DocumentedBlock, Refactoring, Severity


@pytest.fixture
def analysis() -> CodeAnalysis:
    """A valid analysis object."""
    return CodeAnalysis(
        language="Python",
        summary="Adds two numbers.",
        key_points=["Performs no validation."],
        blocks=[
            DocumentedBlock(
                lines="1-2",
                heading="Addition helper",
                explanation="Returns the sum of its two arguments.",
            )
        ],
        refactorings=[
            Refactoring(
                title="Add type hints",
                severity=Severity.LOW,
                lines="1",
                rationale="The signature is untyped.",
                suggestion="def add(a: int, b: int) -> int:",
            )
        ],
    )


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Run every test in a clean directory with no inherited configuration.

    Without this a developer's real ``.env`` or exported ``GEMINI_API_KEY``
    would leak into the config tests and change their outcome.
    """
    for name in (
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "REQUEST_TIMEOUT",
        "MAX_RETRIES",
        "MAX_SNIPPET_CHARS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
