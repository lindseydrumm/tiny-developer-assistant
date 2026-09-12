"""Provider instantiation, retries, and schema validation.

This is the only module in the application that imports the provider SDK
(CONSTITUTION.md I.2). Everything above it depends on the
:class:`StructuredLLMClient` protocol, so swapping providers means adding a
sibling class here and changing :func:`build_client` -- nothing else.

Two invariants this module upholds:

* Nothing leaves ``generate_structured`` except a validated instance of the
  caller's schema. Raw model text never escapes (CONSTITUTION.md II.2).
* Every provider exception is translated into a :mod:`code_explainer.core.errors`
  type carrying a message a user can act on (CONSTITUTION.md III.2).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from code_explainer.config import Settings
from code_explainer.core.errors import (
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
    ResponseValidationError,
    ServiceError,
    TimeoutError_,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

#: Status codes worth retrying: throttling plus transient upstream failures.
_RETRYABLE_STATUS = [429, 500, 502, 503, 504]

#: Substrings that mark a 400 as a credentials problem rather than a bad request.
#: Gemini reports an invalid key as 400 INVALID_ARGUMENT, so the status code
#: alone is not enough to tell the two apart.
_AUTH_HINTS = ("api key not valid", "api_key_invalid", "invalid api key")


class StructuredLLMClient(Protocol):
    """The narrow surface the analyzer depends on."""

    def generate_structured(
        self,
        *,
        system_instruction: str,
        prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT:
        """Return an instance of ``schema`` built from the model's response."""
        ...


class GeminiClient:
    """A :class:`StructuredLLMClient` backed by Google's Gemini models."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.gemini_model
        retry_options = types.HttpRetryOptions(
            # `attempts` counts the original request, so N retries is N+1 attempts.
            attempts=settings.max_retries + 1,
            http_status_codes=_RETRYABLE_STATUS,
        )
        try:
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    # The SDK takes milliseconds; our setting is in seconds.
                    timeout=int(settings.request_timeout * 1000),
                    retry_options=retry_options,
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise ConfigurationError(
                f"Could not initialize the Gemini client: {exc}"
            ) from exc

    def generate_structured(
        self,
        *,
        system_instruction: str,
        prompt: str,
        schema: type[SchemaT],
    ) -> SchemaT:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            # We declare no tools and want no tool calls: this asks for one
            # JSON document and nothing else. Disabling AFC also silences the
            # SDK's advisory warning about it on every request.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except genai_errors.APIError as exc:
            raise _translate_api_error(exc, self._model) from exc
        except httpx.TimeoutException as exc:
            raise TimeoutError_(
                f"The request to Gemini timed out. Retry, raise REQUEST_TIMEOUT "
                f"in your .env, or analyze a smaller snippet. ({exc})"
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Could not reach the Gemini API. Check your network connection. ({exc})"
            ) from exc

        return _extract(response, schema)


def _translate_api_error(exc: genai_errors.APIError, model: str) -> Exception:
    """Map a provider error onto our hierarchy with an actionable message."""
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    lowered = message.lower()

    if code in (401, 403) or any(hint in lowered for hint in _AUTH_HINTS):
        return AuthenticationError(
            "Gemini rejected the API key. Confirm GEMINI_API_KEY in your .env "
            "matches a key from https://aistudio.google.com/apikey and that the "
            f"key has not been revoked. (provider said: {message})"
        )

    if code == 429:
        return RateLimitError(
            "Gemini's free-tier rate limit is exhausted and retries did not "
            "clear it. Wait a minute and try again, raise MAX_RETRIES, or move "
            f"to a paid key. (provider said: {message})"
        )

    if code == 404:
        return ServiceError(
            f"Gemini has no model named '{model}' available to this key. Check "
            f"GEMINI_MODEL in your .env. (provider said: {message})"
        )

    if code is not None and 500 <= code < 600:
        return ServiceError(
            "Gemini returned a server-side error and retries did not clear it. "
            f"This is usually transient -- try again shortly. (provider said: {message})"
        )

    return ServiceError(f"Gemini rejected the request (HTTP {code}): {message}")


def _extract(response: types.GenerateContentResponse, schema: type[SchemaT]) -> SchemaT:
    """Pull a validated ``schema`` instance out of a provider response.

    Every path that does not yield a fully valid object raises; no partially
    populated or unvalidated value is ever returned.
    """
    _reject_blocked_prompt(response)
    _reject_truncated(response)

    # Fast path: the SDK already built our schema from well-formed JSON.
    if isinstance(response.parsed, schema):
        return response.parsed

    # Otherwise validate the raw body ourselves. Two reasons not to lean on
    # `response.parsed` alone: it is None whenever the model answered with
    # prose or malformed JSON, and its declared type is a loose union that
    # silently coerces an unrecognised payload into a bare BaseModel. Going
    # back to the text keeps this the real enforcement point for
    # CONSTITUTION.md II.2 and yields field-level errors worth showing a user.
    raw = response.text
    if not raw or not raw.strip():
        raise ResponseValidationError(
            "Gemini returned an empty response body. This is usually transient "
            "-- try again."
        )

    try:
        return schema.model_validate_json(raw)
    except ValidationError as exc:
        raise ResponseValidationError(_describe_invalid(exc, raw)) from exc


def _reject_blocked_prompt(response: types.GenerateContentResponse) -> None:
    """Raise if the provider's safety filters refused the input outright."""
    feedback = response.prompt_feedback
    block_reason = getattr(feedback, "block_reason", None) if feedback else None
    if block_reason:
        raise ResponseValidationError(
            f"Gemini declined to analyze this snippet (reason: {block_reason}). "
            "Its safety filters occasionally misfire on security-related code; "
            "analyzing a smaller excerpt often gets through."
        )


def _reject_truncated(response: types.GenerateContentResponse) -> None:
    """Raise if generation stopped early, which leaves the JSON unterminated."""
    candidates = response.candidates or []
    if not candidates:
        raise ResponseValidationError(
            "Gemini returned an empty response with no candidates. This is "
            "usually transient -- try again."
        )

    finish_reason = candidates[0].finish_reason
    if finish_reason == types.FinishReason.MAX_TOKENS:
        raise ResponseValidationError(
            "Gemini hit its output limit before finishing, so the analysis was "
            "cut off mid-JSON. Analyze a smaller snippet, or split this one up."
        )


def _describe_invalid(exc: ValidationError, raw: str | None) -> str:
    """Render a validation failure as a short, readable report.

    Distinguishes "that wasn't JSON at all" (the model answered in prose) from
    "that was JSON but the wrong shape" (fields missing or mistyped), because
    the two point at different fixes.
    """
    problems = exc.errors()

    if any(str(problem["type"]).startswith("json_") for problem in problems):
        headline = "Gemini did not return valid JSON."
    else:
        detail = "\n".join(
            f"  - {'.'.join(str(part) for part in problem['loc']) or '<root>'}: {problem['msg']}"
            for problem in problems[:5]
        )
        more = len(problems) - 5
        if more > 0:
            detail += f"\n  ... and {more} more"
        headline = f"Gemini returned JSON that does not match the expected schema:\n{detail}"

    return (
        f"{headline}\n"
        "This usually clears on a retry; a smaller snippet or a stronger model "
        "(set GEMINI_MODEL=gemini-2.5-pro) makes it less likely.\n"
        f"Response began: {_excerpt(raw)}"
    )


def _excerpt(text: str | None, limit: int = 300) -> str:
    """Return a short single-line preview of a response body for error messages."""
    if not text:
        return "<empty>"
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + " ..."


def build_client(settings: Settings) -> StructuredLLMClient:
    """Construct the configured provider client.

    The single place that names a concrete provider. Adding a second backend
    means adding a branch here, not touching the analyzer or the CLI.
    """
    return GeminiClient(settings)
