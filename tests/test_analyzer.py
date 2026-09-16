"""Analyzer orchestration, exercised against a fake client (no network)."""

from __future__ import annotations

import pytest

from dev_assistant.core.analyzer import AnalysisRequest, CodeAnalyzer
from dev_assistant.core.errors import InputValidationError
from dev_assistant.core.prompts import SYSTEM_PROMPT, CodeAnalysis


class FakeClient:
    """Records what it was asked and replays a canned analysis."""

    def __init__(self, result: CodeAnalysis) -> None:
        self.result = result
        self.calls: list[dict] = []

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.calls.append(
            {"system_instruction": system_instruction, "prompt": prompt, "schema": schema}
        )
        return self.result


class TestAnalyze:
    def test_returns_the_validated_analysis(self, analysis):
        analyzer = CodeAnalyzer(FakeClient(analysis))

        result = analyzer.analyze(AnalysisRequest(code="def add(a, b):\n    return a + b"))

        assert result is analysis

    def test_passes_system_prompt_and_schema(self, analysis):
        client = FakeClient(analysis)
        analyzer = CodeAnalyzer(client)

        analyzer.analyze(AnalysisRequest(code="x = 1"))

        call = client.calls[0]
        assert call["system_instruction"] == SYSTEM_PROMPT
        assert call["schema"] is CodeAnalysis

    def test_forwards_context_into_the_prompt(self, analysis):
        client = FakeClient(analysis)
        analyzer = CodeAnalyzer(client)

        analyzer.analyze(
            AnalysisRequest(
                code="x = 1",
                language="Python",
                filename="settings.py",
                focus="is this thread safe?",
            )
        )

        prompt = client.calls[0]["prompt"]
        assert "settings.py" in prompt
        assert "Python" in prompt
        assert "is this thread safe?" in prompt

    def test_numbers_the_lines_it_sends(self, analysis):
        client = FakeClient(analysis)
        analyzer = CodeAnalyzer(client)

        analyzer.analyze(AnalysisRequest(code="first\nsecond"))

        prompt = client.calls[0]["prompt"]
        assert "1 | first" in prompt
        assert "2 | second" in prompt


class TestInputValidation:
    """Bad input must be rejected locally, before it costs an API call."""

    @pytest.mark.parametrize("code", ["", "   ", "\n\n\t "])
    def test_rejects_blank_input(self, analysis, code):
        client = FakeClient(analysis)
        analyzer = CodeAnalyzer(client)

        with pytest.raises(InputValidationError, match="empty"):
            analyzer.analyze(AnalysisRequest(code=code))

        assert client.calls == []

    def test_rejects_oversized_input(self, analysis):
        client = FakeClient(analysis)
        analyzer = CodeAnalyzer(client, max_snippet_chars=50)

        with pytest.raises(InputValidationError, match="over the"):
            analyzer.analyze(AnalysisRequest(code="x" * 51))

        assert client.calls == []

    def test_accepts_input_at_the_limit(self, analysis):
        analyzer = CodeAnalyzer(FakeClient(analysis), max_snippet_chars=50)

        assert analyzer.analyze(AnalysisRequest(code="x" * 50)) is analysis
