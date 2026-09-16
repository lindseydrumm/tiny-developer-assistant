"""A minimal progress indicator while the model is working.

Part of the interface layer: ``core`` never reports progress, it just takes
time. The analyzer stays unaware that anything is watching it.

Everything is written to **stderr** and nothing is written at all unless that 
stream is a terminal."""

from __future__ import annotations

import itertools
import sys
import threading
import time
from types import TracebackType
from typing import IO, Optional

#: Preferred frames. Falls back to ASCII on terminals that cannot encode these.
_BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_ASCII = "-\\|/"


def _frames_for(stream: IO[str]) -> str:
    """Pick the richest frame set the stream's encoding can actually render."""
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        _BRAILLE.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return _ASCII
    return _BRAILLE


class Spinner:
    """Animate a one-line status on stderr while output loads that does not show up
    outside of a terminal, like when the output is saved.  """

    def __init__(
        self,
        message: str,
        *,
        stream: Optional[IO[str]] = None,
        interval: float = 0.1,
    ) -> None:
        self._message = message
        self._stream = stream if stream is not None else sys.stderr
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def active(self) -> bool:
        """True when this spinner will actually draw."""
        try:
            return bool(self._stream.isatty())
        except (AttributeError, ValueError):
            # A closed or non-stream object: stay silent rather than crash.
            return False

    def __enter__(self) -> "Spinner":
        if self.active:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Stop and erase the line.

        Returns ``None`` so the caller's error message must can still reach 
        the user, on a clean line.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
            self._erase()

    def _spin(self) -> None:
        frames = _frames_for(self._stream)
        for frame in itertools.cycle(frames):
            if self._stop.is_set():
                return
            self._write(f"\r{frame} {self._message}")
            # Wait on the event rather than sleeping, so stopping is immediate
            # instead of up to one interval late.
            if self._stop.wait(self._interval):
                return

    def _erase(self) -> None:
        """Blank the status line so the next output starts clean."""
        self._write("\r" + " " * (len(self._message) + 2) + "\r")

    def _write(self, text: str) -> None:
        try:
            self._stream.write(text)
            self._stream.flush()
        except (OSError, ValueError):
            # The stream closed under us; give up quietly rather than raising
            # from a background thread.
            self._stop.set()
