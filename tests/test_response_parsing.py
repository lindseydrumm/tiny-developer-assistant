"""Response parsing and provider-error translation.

These cover the CONSTITUTION.md II.2 boundary: the assertions below are what
stops unvalidated model output from reaching core logic.
"""

from __future__ import annotations

import json

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from code_explainer.core.errors import (
    AuthenticationError,
    RateLimitError,
    ResponseValidationError,
    ServiceError,
)
from code_explainer.core.llm_client import (
    _excerpt,
    _extract,
    _translate_api_error,
)
from code_explainer.core.prompts import CodeAnalysis, Severity
from tests.helpers import analysis_payload, make_response


class TestExtract:
    """`_extract` must return a valid object or raise -- never anything else."""

    def test_returns_sdk_parsed_instance(self, analysis):
        response = make_response(text=analysis.model_dump_json(), parsed=analysis)

        result = _extract(response, CodeAnalysis)

        assert isinstance(result, CodeAnalysis)
        assert result.summary == "Adds two numbers."
        assert result.refactorings[0].severity is Severity.LOW

    def test_recovers_valid_json_the_sdk_left_unparsed(self):
        """`parsed` is None on some responses; the raw body is still usable."""
        response = make_response(text=json.dumps(analysis_payload()), parsed=None)

        result = _extract(response, CodeAnalysis)

        assert isinstance(result, CodeAnalysis)
        assert result.blocks[0].heading == "Addition helper"
        # The enum must be coerced, not left as a bare string.
        assert result.refactorings[0].severity is Severity.LOW

    def test_rejects_json_missing_required_fields(self):
        payload = analysis_payload()
        del payload["summary"]
        response = make_response(text=json.dumps(payload), parsed=None)

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        message = str(caught.value)
        assert "summary" in message
        assert "does not match the expected schema" in message

    def test_rejects_bad_enum_value(self):
        payload = analysis_payload()
        payload["refactorings"][0]["severity"] = "catastrophic"
        response = make_response(text=json.dumps(payload), parsed=None)

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "severity" in str(caught.value)

    def test_rejects_nested_type_error(self):
        payload = analysis_payload()
        payload["key_points"] = "not a list of strings"
        response = make_response(text=json.dumps(payload), parsed=None)

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "key_points" in str(caught.value)

    def test_rejects_prose(self):
        """The common failure: the model answers in prose instead of JSON."""
        response = make_response(
            text="Sure! Here's an explanation of your code...", parsed=None
        )

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        message = str(caught.value)
        assert "did not return valid JSON" in message
        assert "Sure! Here's an explanation" in message

    def test_rejects_empty_body(self):
        response = make_response(text="   ", parsed=None)

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "empty response body" in str(caught.value)

    def test_rejects_truncated_output(self):
        response = make_response(
            text='{"language": "Python", "summary": "Adds tw',
            parsed=None,
            finish_reason=types.FinishReason.MAX_TOKENS,
        )

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "output limit" in str(caught.value)

    def test_rejects_blocked_prompt(self):
        response = make_response(
            text=None,
            parsed=None,
            block_reason=types.BlockedReason.SAFETY,
        )

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "declined to analyze" in str(caught.value)

    def test_rejects_empty_response(self):
        response = make_response(with_candidate=False)

        with pytest.raises(ResponseValidationError) as caught:
            _extract(response, CodeAnalysis)

        assert "no candidates" in str(caught.value)


class TestTranslateApiError:
    """Provider errors must become actionable messages, not raw HTTP noise."""

    @staticmethod
    def _api_error(code: int, message: str) -> genai_errors.APIError:
        return genai_errors.APIError(
            code, {"error": {"code": code, "message": message, "status": "ERROR"}}
        )

    def test_invalid_key_reported_as_auth_error(self):
        """Gemini returns 400, not 401, for a bad key -- match on the message."""
        error = self._api_error(400, "API key not valid. Please pass a valid API key.")

        result = _translate_api_error(error, "gemini-2.5-flash")

        assert isinstance(result, AuthenticationError)
        assert "GEMINI_API_KEY" in str(result)

    def test_403_reported_as_auth_error(self):
        result = _translate_api_error(self._api_error(403, "Forbidden"), "m")

        assert isinstance(result, AuthenticationError)

    def test_429_reported_as_rate_limit(self):
        result = _translate_api_error(self._api_error(429, "Quota exceeded"), "m")

        assert isinstance(result, RateLimitError)
        assert "rate limit" in str(result)

    def test_404_names_the_model_and_the_setting(self):
        result = _translate_api_error(self._api_error(404, "not found"), "gemini-9-ultra")

        assert isinstance(result, ServiceError)
        assert "gemini-9-ultra" in str(result)
        assert "GEMINI_MODEL" in str(result)

    def test_500_reported_as_transient(self):
        result = _translate_api_error(self._api_error(503, "overloaded"), "m")

        assert isinstance(result, ServiceError)
        assert "transient" in str(result)

    def test_unexpected_status_still_translated(self):
        result = _translate_api_error(self._api_error(418, "teapot"), "m")

        assert isinstance(result, ServiceError)
        assert "418" in str(result)


class TestExcerpt:
    def test_handles_empty(self):
        assert _excerpt(None) == "<empty>"
        assert _excerpt("") == "<empty>"

    def test_collapses_whitespace(self):
        assert _excerpt("a\n\n  b\tc") == "a b c"

    def test_truncates_with_marker(self):
        result = _excerpt("x" * 500, limit=100)

        assert result.endswith(" ...")
        assert len(result) == 104
