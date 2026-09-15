"""The spinner must be invisible to anything that is not a live terminal."""

from __future__ import annotations

import io
import time

import pytest

from dev_assistant.interface.progress import _ASCII, _BRAILLE, Spinner, _frames_for


class FakeStream:
    """A text sink that can pretend to be (or not be) a terminal.

    Wraps a StringIO rather than subclassing it, because ``encoding`` is
    read-only on the real class and these tests need to vary it.
    """

    def __init__(self, *, isatty: bool, encoding: str = "utf-8") -> None:
        self._buffer = io.StringIO()
        self._isatty = isatty
        self.encoding = encoding

    def isatty(self) -> bool:
        return self._isatty

    def write(self, text: str) -> int:
        return self._buffer.write(text)

    def flush(self) -> None:
        self._buffer.flush()

    def getvalue(self) -> str:
        return self._buffer.getvalue()


class TestQuietWhenNotATerminal:
    def test_writes_nothing_to_a_pipe(self):
        """Redirected output must be byte-for-byte unchanged."""
        stream = FakeStream(isatty=False)

        with Spinner("Analyzing", stream=stream, interval=0.01):
            time.sleep(0.05)

        assert stream.getvalue() == ""

    def test_reports_itself_inactive(self):
        assert not Spinner("x", stream=FakeStream(isatty=False)).active

    def test_survives_a_stream_without_isatty(self):
        """An odd stand-in stream should silence the spinner, not crash it."""

        class Bare:
            def write(self, text): ...
            def flush(self): ...

        spinner = Spinner("x", stream=Bare())  # type: ignore[arg-type]

        assert not spinner.active
        with spinner:
            pass


class TestDrawsOnATerminal:
    def test_animates_then_erases(self):
        stream = FakeStream(isatty=True)

        with Spinner("Analyzing", stream=stream, interval=0.01):
            time.sleep(0.08)

        output = stream.getvalue()
        assert "Analyzing" in output
        assert any(frame in output for frame in _BRAILLE)
        # The final write must blank the line so real output starts clean.
        assert output.endswith("\r" + " " * len("Analyzing  ") + "\r")

    def test_leaves_no_visible_text_behind(self):
        stream = FakeStream(isatty=True)

        with Spinner("Working", stream=stream, interval=0.01):
            time.sleep(0.05)

        # Whatever was drawn, the last carriage return wipes the line.
        final_line = stream.getvalue().rsplit("\r", 2)[-2]
        assert final_line.strip() == ""


class TestExceptionSafety:
    def test_does_not_swallow_exceptions(self):
        """An error during the call must still reach the caller."""
        stream = FakeStream(isatty=True)

        with pytest.raises(RuntimeError, match="boom"):
            with Spinner("Analyzing", stream=stream, interval=0.01):
                raise RuntimeError("boom")

    def test_erases_before_an_exception_propagates(self):
        """So the error message is not printed on top of the spinner."""
        stream = FakeStream(isatty=True)

        with pytest.raises(RuntimeError):
            with Spinner("Analyzing", stream=stream, interval=0.01):
                time.sleep(0.03)
                raise RuntimeError("boom")

        assert stream.getvalue().endswith("\r")

    def test_stops_its_thread(self):
        stream = FakeStream(isatty=True)
        spinner = Spinner("Analyzing", stream=stream, interval=0.01)

        with spinner:
            time.sleep(0.03)

        assert spinner._thread is None


class TestFrameSelection:
    def test_prefers_braille_on_utf8(self):
        assert _frames_for(FakeStream(isatty=True, encoding="utf-8")) == _BRAILLE

    def test_falls_back_to_ascii_on_a_limited_terminal(self):
        assert _frames_for(FakeStream(isatty=True, encoding="ascii")) == _ASCII

    def test_falls_back_on_an_unknown_encoding(self):
        assert _frames_for(FakeStream(isatty=True, encoding="not-a-codec")) == _ASCII
