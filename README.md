# Code Explainer

Takes a code snippet, asks an LLM to analyze it, and prints structured
documentation: a **summary**, **block-by-block documentation**, and
**suggested refactorings**.

Runs on Google Gemini's free tier — no billing setup required.

```
$ explain config_loader.py

config_loader.py  (Python)
==========================

SUMMARY
-------
  Parses a config file into a dictionary and applies defaults for any keys the file
  omits. Callers treat the result as the single source of truth for runtime settings.

  - Silently ignores unknown keys.
  - Reads the file on every call rather than caching it.
  - Raises nothing on a malformed file; returns partial data instead.

DOCUMENTATION
-------------
  [1-4] Imports and defaults
      Establishes the DEFAULTS mapping used to backfill absent keys. Defined at module
      scope so it is shared across calls.

  [6-18] load_config
      Opens the path, parses each line as key=value, and merges the result over
      DEFAULTS. Lines without an equals sign are skipped.

SUGGESTED REFACTORINGS
----------------------
  1. [HIGH] Fail loudly on a malformed line  (12-14)
      Skipping unparseable lines hides typos in config, which surface much later as
      puzzling default values.

      Raise a ConfigError naming the file and line number instead of continuing.
```

## Setup

Requires Python 3.10 or newer.

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Get a free API key from https://aistudio.google.com/apikey

# 3. Configure
cp .env.example .env
# then paste your key into .env
```

`.env` is git-ignored. The application reads configuration only from the
environment — no key is ever stored in source.

## Usage

```bash
explain path/to/file.py              # analyze a file
cat file.py | explain                # or read from stdin
explain file.py --json               # machine-readable output

explain file.py -l Rust              # give a language hint
explain file.py -f "is this thread safe?"   # steer the analysis
explain file.py -m gemini-2.5-pro    # use a different model for one run
```

| Flag | Short | Purpose |
|---|---|---|
| `--language` | `-l` | Language hint. Inferred when omitted. |
| `--focus` | `-f` | A question to steer the analysis. |
| `--model` | `-m` | Override `GEMINI_MODEL` for one run. |
| `--json` | | Emit the validated JSON instead of prose. |
| `--version` | | Print the version and exit. |

### Configuration

Every setting is read from the environment or `.env`. Only the key is required.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google AI Studio key. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any model your key can reach. |
| `REQUEST_TIMEOUT` | `60.0` | Per-request timeout, in seconds. |
| `MAX_RETRIES` | `3` | Retries for throttling and server errors. |
| `MAX_SNIPPET_CHARS` | `100000` | Reject larger snippets before spending a request. |

### A note on the free tier

`gemini-2.5-flash` has a generous free quota and is the default.
`gemini-2.5-pro` gives noticeably better analysis on dense code but has a much
lower free daily limit — worth switching to per-run with `-m` when a snippet
warrants it.

When the quota runs out you get a clear message, not a stack trace:

```
Error: Gemini's free-tier rate limit is exhausted and retries did not clear it.
Wait a minute and try again, raise MAX_RETRIES, or move to a paid key.
```

## Architecture

Three layers, with dependencies pointing one direction only. `core` never
imports from `interface`.

```
interface/cli.py          argv, files, stdout. The only layer that prints.
        |
core/analyzer.py          orchestration + input validation. No UI, no SDK.
        |
core/llm_client.py        the only module that imports the provider SDK.
        |
core/prompts.py           system prompt + response schema. No I/O, no imports
                          from the rest of the app.
```

Supporting modules: `config.py` (environment-only settings) and
`core/errors.py` (the exception hierarchy the CLI renders).

**Swapping providers** means adding a class next to `GeminiClient` that
satisfies the `StructuredLLMClient` protocol and changing `build_client()`.
The analyzer and CLI are untouched — they only ever see the protocol and a
validated `CodeAnalysis`.

### Structured output

The model is asked for JSON matching the `CodeAnalysis` Pydantic schema, and
`llm_client._extract` is the single gate it must pass:

- if the SDK already produced a `CodeAnalysis`, it is returned;
- otherwise the raw body is re-validated with `model_validate_json`;
- anything else — prose, truncated JSON, missing fields, a bad enum — raises
  `ResponseValidationError` naming the offending field.

Unvalidated model text never reaches the analyzer or the CLI.

### Safety

Snippets are treated strictly as inert text. Nothing in the package calls
`eval`, `exec`, `compile`, `import`, or a subprocess on user input, and the
system prompt instructs the model to describe the code rather than run it — and
to ignore any instructions embedded in comments or string literals.

### Errors

Every failure the user can act on has its own exception type and exit code, and
the CLI prints the message rather than a traceback.

| Exit | Meaning |
|---|---|
| `64` | Bad input — missing file, empty snippet, snippet too large. |
| `65` | The model's response failed schema validation. |
| `69` | Provider unreachable, or a server-side error that retries did not clear. |
| `75` | Rate limited, or timed out. |
| `77` | The API key was rejected. |
| `78` | Configuration problem — usually `GEMINI_API_KEY` is not set. |

## Development

```bash
pytest              # 68 tests, no network, no credentials
```

The suite builds real `google.genai` response objects rather than mocks, so
the parsing tests exercise the same object shape the SDK returns. Coverage
focuses on the response-parsing boundary: valid responses, prose instead of
JSON, truncated output, missing and mistyped fields, safety blocks, and the
translation of each provider error into an actionable message.
