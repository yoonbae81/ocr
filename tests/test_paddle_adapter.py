import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from adapters.recognition import MlxPaddleRecognizerAdapter
from domain import PageNumber, SourcePage


def test_adapter_passes_mlx_server_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, str] = {}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs: str) -> None:
            recorded.update(kwargs)

    fake_module = ModuleType("paddleocr")
    fake_module.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    MlxPaddleRecognizerAdapter(
        "http://127.0.0.1:1234", "matrixmaven/PaddleOCR-VL-1.6-MLX"
    )

    assert recorded == {
        "vl_rec_backend": "mlx-vlm-server",
        "vl_rec_server_url": "http://127.0.0.1:1234",
        "vl_rec_api_model_name": "matrixmaven/PaddleOCR-VL-1.6-MLX",
    }


def test_adapter_recognizes_page_batch_with_one_pipeline_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[str] = []

    class FakeResult:
        def __init__(self, text: str) -> None:
            self.markdown = {"markdown_texts": text}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs: str) -> None:
            del kwargs

        def predict_iter(self, inputs: list[str]) -> Iterator[FakeResult]:
            received.extend(inputs)
            for input_path in inputs:
                yield FakeResult(f"raw {Path(input_path).stem}")

    fake_module = ModuleType("paddleocr")
    fake_module.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)
    pages = tuple(
        SourcePage(PageNumber(number), tmp_path / f"{number}.jpg")
        for number in range(1, 4)
    )

    results = tuple(
        MlxPaddleRecognizerAdapter(
            "http://127.0.0.1:1234", "model"
        ).recognize_many(pages)
    )

    assert received == [str(page.image_path) for page in pages]
    assert [result.text for result in results] == ["raw 1", "raw 2", "raw 3"]


def test_adapter_configures_vl_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_concurrency = 6
    recorded: dict[str, str | int] = {}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs: str | int) -> None:
            recorded.update(kwargs)

    fake_module = ModuleType("paddleocr")
    fake_module.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    MlxPaddleRecognizerAdapter(
        "http://127.0.0.1:1234",
        "model",
        max_concurrency=expected_concurrency,
    )

    assert recorded["vl_rec_max_concurrency"] == expected_concurrency
