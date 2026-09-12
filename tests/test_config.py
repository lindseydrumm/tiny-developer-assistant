"""Configuration loading and the secrets boundary (CONSTITUTION.md II.1)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from code_explainer import config
from code_explainer.config import Settings, load_settings
from code_explainer.core.errors import ConfigurationError
from tests.helpers import PLACEHOLDER_KEY


class TestLoadSettings:
    def test_missing_key_gives_setup_instructions(self):
        with pytest.raises(ConfigurationError) as caught:
            load_settings()

        message = str(caught.value)
        assert "GEMINI_API_KEY is not set" in message
        assert "aistudio.google.com/apikey" in message
        assert ".env.example" in message

    def test_reads_the_key_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)

        settings = load_settings()

        assert settings.gemini_api_key == PLACEHOLDER_KEY

    def test_reads_a_dotenv_file(self, tmp_path, monkeypatch):
        Path(tmp_path, ".env").write_text(f"GEMINI_API_KEY={PLACEHOLDER_KEY}\n")

        settings = load_settings()

        assert settings.gemini_api_key == PLACEHOLDER_KEY

    def test_defaults_to_a_free_tier_model(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)

        assert load_settings().gemini_model == "gemini-2.5-flash"

    def test_environment_overrides_the_defaults(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
        monkeypatch.setenv("MAX_RETRIES", "7")

        settings = load_settings()

        assert settings.gemini_model == "gemini-2.5-pro"
        assert settings.max_retries == 7

    def test_explicit_overrides_beat_the_environment(self, monkeypatch):
        """The CLI's --model flag arrives this way."""
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

        assert load_settings(gemini_model="gemini-2.5-pro").gemini_model == "gemini-2.5-pro"

    def test_blank_key_is_rejected(self, monkeypatch):
        """An empty assignment in .env must fail here, not at the API."""
        monkeypatch.setenv("GEMINI_API_KEY", "")

        with pytest.raises(ConfigurationError):
            load_settings()

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("MAX_RETRIES", "-1"),
            ("REQUEST_TIMEOUT", "0"),
            ("MAX_SNIPPET_CHARS", "0"),
        ],
    )
    def test_out_of_range_values_are_reported_clearly(self, monkeypatch, name, value):
        monkeypatch.setenv("GEMINI_API_KEY", PLACEHOLDER_KEY)
        monkeypatch.setenv(name, value)

        with pytest.raises(ConfigurationError) as caught:
            load_settings()

        assert "Invalid configuration" in str(caught.value)


class TestSecretsBoundary:
    def test_the_api_key_field_has_no_default(self):
        """CONSTITUTION.md II.1 -- a default here would be a hardcoded secret."""
        assert Settings.model_fields["gemini_api_key"].is_required()

    def test_the_config_module_contains_no_key_literal(self):
        """Guards against a key being pasted in during debugging."""
        source = inspect.getsource(config)

        assert "AIza" not in source  # Google API keys start with this prefix.
