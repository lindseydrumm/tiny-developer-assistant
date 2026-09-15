"""Command-line entry point.

The only layer that reads argv, touches the filesystem, or writes to a stream.
It catches :class:`~dev-assistant.core.errors.CodeExplainerError` and prints
``str(exc)`` -- users see guidance, never a traceback (CONSTITUTION.md III.2).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Optional

import typer

from dev-assistant import __version__
from dev-assistant.config import load_settings
from dev-assistant.core.analyzer import AnalysisRequest, build_analyzer
from dev-assistant.core.errors import CodeExplainerError, InputValidationError
from dev-assistant.core.prompts import CodeAnalysis, Severity

app = typer.Typer(
    add_completion=False,
    help="Explain a code snippet: summary, block-by-block docs, and suggested refactorings.",
)

_WIDTH = 88

_SEVERITY_COLOR = {
    Severity.HIGH: typer.colors.RED,
    Severity.MEDIUM: typer.colors.YELLOW,
    Severity.LOW: typer.colors.BLUE,
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"code-explainer {__version__}")
        raise typer.Exit()


@app.command()
def explain(
    path: Optional[Path] = typer.Argument(
        None,
        help="File to analyze. Omit it, or pass '-', to read from stdin.",
        exists=False,
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "-l", help="Language hint. Inferred when omitted."
    ),
    focus: Optional[str] = typer.Option(
        None,
        "--focus",
        "-f",
        help="A question to steer the analysis, e.g. 'is this thread safe?'.",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override GEMINI_MODEL for this run."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the raw validated JSON instead of prose."
    ),
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Analyze a code snippet and print structured documentation."""
    try:
        code, source_name = _read_source(path)

        overrides = {"gemini_model": model} if model else {}
        settings = load_settings(**overrides)

        analyzer = build_analyzer(settings)
        analysis = analyzer.analyze(
            AnalysisRequest(
                code=code,
                language=language,
                filename=source_name,
                focus=focus,
            )
        )
    except CodeExplainerError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=exc.exit_code) from exc

    if as_json:
        typer.echo(analysis.model_dump_json(indent=2))
    else:
        _render(analysis, source_name)


def _read_source(path: Optional[Path]) -> tuple[str, Optional[str]]:
    """Return ``(code, display_name)`` from a file or stdin.

    The file is read as text and passed along as text. Nothing here imports,
    compiles, or runs it (CONSTITUTION.md II.3).
    """
    if path is None or str(path) == "-":
        # A bare `explain` in a terminal is almost always a mistake, so it gets
        # usage help. An explicit `-` is the conventional "I mean stdin", so it
        # opens for typing or pasting instead.
        asked_for_stdin = path is not None
        if sys.stdin.isatty():
            if not asked_for_stdin:
                raise InputValidationError(
                    "No input. Paste a snippet, point at a file, or pipe code in:\n"
                    "  explain -                     paste, then press Ctrl-D\n"
                    "  explain path/to/file.py\n"
                    "  pbpaste | explain             analyze the clipboard"
                )
            typer.secho(
                "Reading from stdin -- paste your code, then press Ctrl-D on a "
                "blank line.",
                fg=typer.colors.BRIGHT_BLACK,
                err=True,
            )
        return sys.stdin.read(), None

    if not path.exists():
        raise InputValidationError(f"No such file: {path}")
    if path.is_dir():
        raise InputValidationError(f"{path} is a directory. Point at a single file.")

    try:
        return path.read_text(encoding="utf-8"), path.name
    except UnicodeDecodeError as exc:
        raise InputValidationError(
            f"{path} is not UTF-8 text. This tool analyzes source files, not binaries."
        ) from exc
    except OSError as exc:
        raise InputValidationError(f"Could not read {path}: {exc}") from exc


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _render(analysis: CodeAnalysis, source_name: Optional[str]) -> None:
    """Print the analysis as readable prose."""
    title = source_name or "snippet"
    _heading(f"{title}  ({analysis.language})")

    _section("SUMMARY")
    _paragraph(analysis.summary)

    if analysis.key_points:
        typer.echo()
        for point in analysis.key_points:
            _bullet(point)

    _section("DOCUMENTATION")
    if not analysis.blocks:
        _paragraph("The model returned no block documentation.")
    for block in analysis.blocks:
        typer.secho(f"  [{block.lines}] ", fg=typer.colors.CYAN, nl=False)
        typer.secho(block.heading, bold=True)
        _paragraph(block.explanation, indent=6)
        typer.echo()

    _section("SUGGESTED REFACTORINGS")
    if not analysis.refactorings:
        _paragraph("None -- the model found nothing worth changing.")
        return

    for index, item in enumerate(analysis.refactorings, start=1):
        color = _SEVERITY_COLOR.get(item.severity, typer.colors.WHITE)
        typer.secho(f"  {index}. [{item.severity.value.upper()}] ", fg=color, nl=False)
        typer.secho(f"{item.title}  ({item.lines})", bold=True)
        _paragraph(item.rationale, indent=6)
        typer.echo()
        _paragraph(item.suggestion, indent=6)
        typer.echo()


def _heading(text: str) -> None:
    typer.echo()
    typer.secho(text, bold=True)
    typer.secho("=" * min(len(text), _WIDTH), bold=True)


def _section(text: str) -> None:
    typer.echo()
    typer.secho(text, fg=typer.colors.GREEN, bold=True)
    typer.secho("-" * len(text), fg=typer.colors.GREEN)


def _paragraph(text: str, indent: int = 2) -> None:
    """Wrap and indent a block of prose, preserving intentional line breaks."""
    prefix = " " * indent
    for line in text.splitlines() or [""]:
        if not line.strip():
            typer.echo()
            continue
        typer.echo(
            textwrap.fill(
                line.strip(),
                width=_WIDTH,
                initial_indent=prefix,
                subsequent_indent=prefix,
            )
        )


def _bullet(text: str) -> None:
    typer.echo(
        textwrap.fill(text, width=_WIDTH, initial_indent="  - ", subsequent_indent="    ")
    )


if __name__ == "__main__":  # pragma: no cover
    app()
