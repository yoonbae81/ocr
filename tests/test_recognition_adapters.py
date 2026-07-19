from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest

from adapters.recognition import recognizer_for
from adapters.recognition.paddle import PaddleAdapter
from domain.content import ImagePage, PageNumber, SourceKind
from settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        paddle_endpoint="http://paddle.test:8111/",
        paddle_model="paddle-model",
    )


@pytest.fixture
def page() -> ImagePage:
    return ImagePage(
        page=PageNumber(1),
        image=b"png bytes",
        media_type="image/png",
        source=SourceKind.IMAGE,
    )


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


def test_paddle_adapter_when_result_is_blank_returns_empty_content(
    page: ImagePage,
) -> None:
    # Given: PaddleOCR-VL returns a result for an intentionally blank page.
    pipeline = FakePaddlePipeline(markdown="")
    adapter = PaddleAdapter(endpoint="endpoint", model="model", pipeline=pipeline)

    # When: the page is recognized.
    result = adapter.recognize(page, "prompt")

    # Then: the empty page is preserved as completed content, not a failure.
    assert result == ""


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
    adapter = recognizer_for(settings=settings)

    # Then: the Paddle adapter receives the configured endpoint and model.
    assert isinstance(adapter, PaddleAdapter)
    assert adapter.endpoint == settings.paddle_endpoint
    assert adapter.model == settings.paddle_model
