from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest

from adapters.recognition import recognizer_for
from adapters.recognition.agy import AgyAdapter
from adapters.recognition.codex import CodexAdapter
from adapters.recognition.errors import (
    RecognitionError,
    UnsupportedEffortError,
    UnsupportedModelError,
)
from adapters.recognition.paddle import PaddleAdapter
from domain.content import ImagePage, PageNumber, SourceKind
from settings import ModelName, Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        paddle_endpoint="http://paddle.test:8111/",
        paddle_model="paddle-model",
        codex_model="codex-model",
        agy_model="agy-model",
        default_model=ModelName.GPT,
    )


@pytest.fixture
def page() -> ImagePage:
    return ImagePage(
        page=PageNumber(1),
        image=b"png bytes",
        media_type="image/png",
        source=SourceKind.IMAGE,
    )


def test_codex_adapter_when_recognizing_passes_image_model_effort_and_prompt(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    page: ImagePage,
) -> None:
    # Given: Codex returns Markdown through its local CLI.
    commands: list[list[str]] = []
    materialized_images: list[tuple[str, bytes]] = []

    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        commands.append(list(command))
        image_path = Path(command[command.index("-i") + 1])
        materialized_images.append((image_path.suffix, image_path.read_bytes()))
        return CompletedProcess(command, 0, stdout="# page", stderr="")

    monkeypatch.setattr("adapters.recognition._cli.subprocess.run", run)
    adapter = CodexAdapter(model=settings.codex_model, effort="high")

    # When: a page is recognized with a caller-supplied prompt.
    result = adapter.recognize(page, "transcribe exactly")

    # Then: the command receives the configured model, effort, prompt, and PNG input.
    assert result == "# page"
    assert commands[0][:2] == ["codex", "exec"]
    assert commands[0][commands[0].index("--model") + 1] == "codex-model"
    assert 'model_reasoning_effort="high"' in commands[0]
    assert commands[0][-1] == "transcribe exactly"
    assert materialized_images == [(".png", b"png bytes")]


def test_agy_adapter_when_recognizing_passes_image_model_and_prompt(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    page: ImagePage,
) -> None:
    # Given: Agy returns Markdown through its local CLI.
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        commands.append(list(command))
        return CompletedProcess(command, 0, stdout="# page", stderr="")

    monkeypatch.setattr("adapters.recognition._cli.subprocess.run", run)
    adapter = AgyAdapter(model=settings.agy_model)

    # When: a page is recognized with a caller-supplied prompt.
    result = adapter.recognize(page, "transcribe exactly")

    # Then: Agy receives the configured model, image path, and prompt without effort.
    assert result == "# page"
    assert commands[0][:4] == ["agy", "--model", "agy-model", "--print"]
    assert commands[0][-1].endswith("transcribe exactly")


@final
class FakePaddleResult:
    def __init__(self, markdown: object) -> None:
        self.markdown: Mapping[str, object] = {"markdown_texts": str(markdown)}
        self.pretty_values: list[bool] = []

    def save_to_markdown(self, save_path: str, *, pretty: bool) -> None:
        self.pretty_values.append(pretty)
        markdown = self.markdown.get("markdown_texts")
        _ = Path(save_path).write_text(
            markdown if isinstance(markdown, str) else "",
            encoding="utf-8",
        )


class FakePaddlePipeline:
    def __init__(self, markdown: str = "# page") -> None:
        self.result: FakePaddleResult = FakePaddleResult(markdown)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def predict(
        self,
        input_path: str,
        *,
        temperature: float,
        max_new_tokens: int,
        **kwargs: object,
    ) -> list[FakePaddleResult]:
        call_kwargs: dict[str, object] = {
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            **kwargs,
        }
        self.calls.append((input_path, call_kwargs))
        return [self.result]


def test_paddle_adapter_when_recognizing_uses_pipeline_and_returns_markdown(
    page: ImagePage,
) -> None:
    # Given: the complete PaddleOCR-VL pipeline returns a Markdown result.
    pipeline = FakePaddlePipeline()
    adapter = PaddleAdapter(
        endpoint="http://paddle.test:8111/",
        model="paddle-model",
        pipeline=pipeline,
    )

    # When: a page is recognized.
    result = adapter.recognize(page, "transcribe exactly")

    # Then: the pipeline receives a temporary PNG and tuned generation parameters.
    assert result == "# page"
    assert pipeline.result.pretty_values == [False]
    assert Path(pipeline.calls[0][0]).suffix == ".png"
    assert pipeline.calls[0][1] == {
        "temperature": 0.0,
        "max_new_tokens": 4096,
        "use_chart_recognition": True,
        "use_ocr_for_image_block": True,
        "markdown_ignore_labels": [],
        "vlm_extra_args": {
            "ocr_min_pixels": None,
            "ocr_max_pixels": None,
            "table_min_pixels": None,
            "table_max_pixels": None,
            "chart_min_pixels": None,
            "chart_max_pixels": None,
            "formula_min_pixels": None,
            "formula_max_pixels": None,
            "seal_min_pixels": None,
            "seal_max_pixels": None,
        },
    }


def test_paddle_adapter_when_result_has_no_markdown_raises_recognition_error(
    page: ImagePage,
) -> None:
    # Given: PaddleOCR-VL returns a malformed result.
    pipeline = FakePaddlePipeline(markdown="")
    pipeline.result.markdown = {}
    adapter = PaddleAdapter(endpoint="endpoint", model="model", pipeline=pipeline)

    # When: PaddleOCR-VL returns no textual content for the page.
    with pytest.raises(RecognitionError, match="empty content"):
        _ = adapter.recognize(page, "prompt")


@pytest.mark.parametrize("model", ["gemini", "paddle"])
def test_recognizer_for_when_effort_is_nondefault_rejects_it(
    settings: Settings,
    model: str,
) -> None:
    # Given: a recognizer that does not expose reasoning-effort configuration.

    # When / Then: the composition boundary rejects an ignored effort flag.
    with pytest.raises(UnsupportedEffortError, match=model):
        _ = recognizer_for(model, settings=settings, effort="high")


def test_recognizer_for_when_model_is_paddle_uses_paddle_adapter(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    # Given: PaddleOCR-VL construction is replaced for a composition test.
    pipeline = FakePaddlePipeline()

    def build_pipeline(_endpoint: str, _model: str) -> FakePaddlePipeline:
        return pipeline

    monkeypatch.setattr("adapters.recognition.paddle._build_pipeline", build_pipeline)

    # When: the Paddle selector is assembled.
    adapter = recognizer_for("paddle", settings=settings, effort="low")

    # Then: the Paddle adapter receives the configured endpoint and model.
    assert isinstance(adapter, PaddleAdapter)
    assert adapter.endpoint == settings.paddle_endpoint
    assert adapter.model == settings.paddle_model


def test_recognizer_for_when_model_is_unknown_raises_unsupported_model_error(
    settings: Settings,
) -> None:
    # Given: an unknown model selector.

    # When / Then: composition rejects it before recognizing a page.
    with pytest.raises(UnsupportedModelError, match="unknown"):
        _ = recognizer_for("unknown", settings=settings, effort="low")


@pytest.mark.parametrize("model", ["gpt", "gemini"])
def test_recognizer_for_when_timeout_is_configured_passes_it_to_cli_adapter(
    settings: Settings,
    model: str,
) -> None:
    # Given: one shared recognition timeout configured at the composition boundary.
    configured = settings.model_copy(update={"recognition_timeout": 17.0})

    # When: a local CLI recognizer is assembled.
    adapter = recognizer_for(model, settings=configured, effort="low")

    # Then: both local adapters receive the same configured timeout.
    assert isinstance(adapter, (CodexAdapter, AgyAdapter))
    assert adapter.timeout == 17.0
