import pytest
from pydantic import ValidationError

from settings import (
    PROJECT_ROOT,
    MissingPaddleConfigurationError,
    Settings,
)


def test_settings_when_loaded_uses_the_project_env_file() -> None:
    # Given: settings have one fixed project location.

    # When: the configuration source is inspected.
    configured_file = Settings.model_config.get("env_file")

    # Then: running from a book workspace still resolves the repository .env.
    assert configured_file == PROJECT_ROOT / ".env"


def test_settings_when_concurrency_is_configured_parses_positive_worker_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the environment limits model requests to three workers.
    monkeypatch.setenv("CONCURRENCY", "3")

    # When: settings are constructed from environment values.
    settings = Settings(
        paddle_endpoint="http://paddle.test:8111/",
        paddle_model="paddle-model",
    )

    # Then: the configured worker count is available to the application layer.
    assert settings.concurrency == 3


def test_settings_when_paddle_is_unconfigured_accepts_empty_values() -> None:
    # Given: no PaddleOCR environment values.

    # When: settings are loaded at the process boundary.
    settings = Settings(
        paddle_endpoint="",
        paddle_model="",
    )

    # Then: construction remains possible until the recognizer is requested.
    assert settings.paddle_endpoint == ""
    assert settings.paddle_model == ""


def test_validate_when_required_paddle_settings_are_missing_reports_fields() -> None:
    # Given: settings with no model-specific configuration.
    settings = Settings(
        paddle_endpoint="",
        paddle_model="",
    )

    # When / Then: validation identifies only the selected model's missing fields.
    with pytest.raises(MissingPaddleConfigurationError) as captured:
        settings.validate_paddle_configuration()
    assert captured.value.fields == ("PADDLE_ENDPOINT", "PADDLE_MODEL")


def test_settings_when_recognition_timeout_is_omitted_uses_shared_default() -> None:
    # Given: settings without an explicit adapter timeout.

    # When: configuration is loaded.
    settings = Settings(
        paddle_endpoint="",
        paddle_model="",
    )

    # Then: local recognition adapters share the documented five-minute limit.
    assert settings.recognition_timeout == 300.0


def test_settings_when_recognition_timeout_is_below_one_rejects_it() -> None:
    # Given: an adapter timeout below the supported boundary.

    # When / Then: settings reject it before an adapter is created.
    with pytest.raises(ValidationError):
        _ = Settings(
            paddle_endpoint="",
            paddle_model="",
            recognition_timeout=0.5,
        )
