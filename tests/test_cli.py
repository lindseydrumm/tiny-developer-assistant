"""CLI behaviour: input handling, rendering, and exit codes.

The analyzer is stubbed out, so these run offline and assert only on what the
interface layer is responsible for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev-assistant.core.analyzer import AnalysisRequest
from dev-assistant.core.errors import (
    AuthenticationError,
    InputValidationError,
    RateLimitError,
)
from dev-assistant.interface import cli
from tests.helpers import PLACEHOLDER_KEY

runner = CliRunner()


class FakeStdin:
    """Stands in for `sys.stdin` so tests can simulate a terminal."""

    def __init__(self, text: str, *, isatty: bool) -> None:
        self._text = text
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty

    def read(self) -> str:
        return self._text


class StubAnalyzer:
    """Stands in for a wired-up CodeAnalyzer."""

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[AnalysisRequest] = []

    def analyze(self, request: AnalysisRequest):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def stub(monkeypatch, analysis):
    """Install a stub analyzer and return it so tests can inspect the call."""
    holder = StubAnalyzer(result=analysis)
    monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
    monkeypatch.setattr(cli, "build_analyzer", lambda settings: holder)
    return holder


def output_of(result) -> str:
    """Combined stdout+stderr, across click versions that separate them."""
    text = result.output or ""
    try:
        text += result.stderr or ""
    except (ValueError, AttributeError):  # stderr not captured separately
        pass
    return text


class TestInput:
    def test_reads_a_file(self, stub, tmp_path):
        target = tmp_path / "sample.py"
        target.write_text("def add(a, b):\n    return a + b\n")

        result = runner.invoke(cli.app, [str(target)])

        assert result.exit_code == 0
        assert stub.requests[0].code.startswith("def add")
        assert stub.requests[0].filename == "sample.py"

    def test_reads_stdin(self, stub):
        result = runner.invoke(cli.app, [], input="x = 1\n")

        assert result.exit_code == 0
        assert stub.requests[0].code == "x = 1\n"
        assert stub.requests[0].filename is None

    def test_dash_means_stdin(self, stub):
        result = runner.invoke(cli.app, ["-"], input="x = 1\n")

        assert result.exit_code == 0
        assert stub.requests[0].code == "x = 1\n"

    def test_forwards_flags(self, stub, tmp_path):
        target = tmp_path / "s.rs"
        target.write_text("fn main() {}")

        runner.invoke(cli.app, [str(target), "-l", "Rust", "-f", "is it safe?"])

        request = stub.requests[0]
        assert request.language == "Rust"
        assert request.focus == "is it safe?"

    def test_model_flag_overrides_settings(self, monkeypatch, analysis):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        seen = {}

        def capture(settings):
            seen["model"] = settings.gemini_model
            return StubAnalyzer(result=analysis)

        monkeypatch.setattr(cli, "build_analyzer", capture)

        runner.invoke(cli.app, ["-m", "gemini-2.5-pro"], input="x = 1")

        assert seen["model"] == "gemini-2.5-pro"

    def test_bare_command_in_a_terminal_shows_usage(self, monkeypatch):
        """No redirection and no argument: the user needs help, not a hang."""
        monkeypatch.setattr(cli.sys, "stdin", FakeStdin("", isatty=True))

        with pytest.raises(InputValidationError) as caught:
            cli._read_source(None)

        message = str(caught.value)
        assert "explain -" in message
        assert "pbpaste | explain" in message

    def test_dash_in_a_terminal_accepts_a_paste(self, monkeypatch):
        """An explicit `-` means stdin even when that stdin is a keyboard."""
        monkeypatch.setattr(
            cli.sys, "stdin", FakeStdin("def add(a, b):\n    return a + b\n", isatty=True)
        )

        code, name = cli._read_source(Path("-"))

        assert code.startswith("def add")
        assert name is None

    def test_rejects_non_utf8_file(self, stub, tmp_path):
        target = tmp_path / "blob.bin"
        target.write_bytes(b"\xff\xfe\x00binary")

        result = runner.invoke(cli.app, [str(target)])

        assert result.exit_code == 64
        assert "not UTF-8" in output_of(result)


class TestRendering:
    def test_prose_output_has_all_three_sections(self, stub):
        result = runner.invoke(cli.app, [], input="x = 1")

        assert result.exit_code == 0
        assert "SUMMARY" in result.output
        assert "DOCUMENTATION" in result.output
        assert "SUGGESTED REFACTORINGS" in result.output

    def test_prose_output_includes_the_content(self, stub):
        result = runner.invoke(cli.app, [], input="x = 1")

        assert "Adds two numbers." in result.output
        assert "Addition helper" in result.output
        assert "Add type hints" in result.output
        assert "[LOW]" in result.output

    def test_json_output_is_valid_and_complete(self, stub):
        result = runner.invoke(cli.app, ["--json"], input="x = 1")

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["summary"] == "Adds two numbers."
        assert payload["refactorings"][0]["severity"] == "low"

    def test_handles_an_analysis_with_no_refactorings(self, stub, analysis):
        stub.result = analysis.model_copy(update={"refactorings": []})

        result = runner.invoke(cli.app, [], input="x = 1")

        assert result.exit_code == 0
        assert "nothing worth changing" in result.output


class TestErrorReporting:
    @pytest.mark.parametrize(
        ("error", "expected_code"),
        [
            (AuthenticationError("bad key"), 77),
            (RateLimitError("slow down"), 75),
        ],
    )
    def test_maps_errors_to_exit_codes(self, monkeypatch, error, expected_code):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        monkeypatch.setattr(
            cli, "build_analyzer", lambda settings: StubAnalyzer(error=error)
        )

        result = runner.invoke(cli.app, [], input="x = 1")

        assert result.exit_code == expected_code
        assert str(error) in output_of(result)

    def test_never_shows_a_traceback(self, monkeypatch):
        """CONSTITUTION.md III.2 -- users get guidance, not stack traces."""
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        monkeypatch.setattr(
            cli,
            "build_analyzer",
            lambda settings: StubAnalyzer(error=AuthenticationError("bad key")),
        )

        result = runner.invoke(cli.app, [], input="x = 1")

        combined = output_of(result)
        assert "Traceback" not in combined
        assert "core/llm_client.py" not in combined

    def test_missing_key_is_reported_cleanly(self, monkeypatch):
        result = runner.invoke(cli.app, [], input="x = 1")

        assert result.exit_code == 78
        assert "GEMINI_API_KEY is not set" in output_of(result)
