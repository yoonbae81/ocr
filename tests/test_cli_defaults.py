from pathlib import Path

import pytest
from typer.testing import CliRunner

from application.ports.recognizer import RecognizerPort
from cli import app
from domain.content import ImagePage
from settings import ModelName, Settings


class SuccessfulRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = (page, prompt)
        return "recognized"


def test_cli_when_model_is_omitted_uses_configured_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: settings select Gemini and no model option is supplied.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(b"png")
    settings = Settings(
        paddle_endpoint="http://paddle.test:8111/",
        paddle_model="paddle-model",
        codex_model="codex-model",
        agy_model="agy-model",
        default_model=ModelName.GEMINI,
    )
    selected_models: list[str] = []

    def factory(model: str, *, settings: Settings, effort: str) -> RecognizerPort:
        _ = (settings, effort)
        selected_models.append(model)
        return SuccessfulRecognizer()

    monkeypatch.setattr("cli._settings", lambda: settings)
    monkeypatch.setattr("cli.recognizer_for", factory)
    monkeypatch.chdir(tmp_path)

    # When: OCR runs without an explicit model option.
    result = CliRunner().invoke(app, ["scan.png", "1"])

    # Then: recognition receives the environment-configured model selection.
    assert result.exit_code == 0
    assert selected_models == ["gemini"]
