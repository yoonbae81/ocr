from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

import pytest

from adapters.recognition import OpenVinoPaddleRecognizerAdapter
from backend_config import OpenVinoBackendConfig
from domain import PageNumber, SourcePage


def test_adapter_configures_pipeline_and_recognizes_in_input_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized: dict[str, object] = {}
    predicted: dict[str, object] = {}

    class FakeResult:
        def __init__(self, text: str) -> None:
            self.markdown = {"markdown_texts": text}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs: object) -> None:
            initialized.update(kwargs)

        def predict(self, inputs: list[str], **kwargs: object) -> Iterable[FakeResult]:
            predicted["inputs"] = inputs
            predicted.update(kwargs)
            return [FakeResult(f"raw {Path(path).stem}") for path in inputs]

    package = ModuleType("paddleocr_vl_openvino")
    pipeline_module = ModuleType(
        "paddleocr_vl_openvino.paddleocr_vl_pipeline"
    )
    pipeline_module.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr_vl_openvino", package)
    monkeypatch.setitem(
        sys.modules,
        "paddleocr_vl_openvino.paddleocr_vl_pipeline",
        pipeline_module,
    )
    model = tmp_path / "vlm"
    layout = tmp_path / "layout.xml"
    config = OpenVinoBackendConfig(
        vlm_model_path=model,
        layout_model_path=layout,
        vlm_batch_size=32,
        max_new_tokens=64,
    )
    pages = tuple(
        SourcePage(PageNumber(number), tmp_path / f"{number}.jpg")
        for number in range(1, 3)
    )

    results = tuple(OpenVinoPaddleRecognizerAdapter(config).recognize_many(pages))

    assert initialized == {
        "vlm_model_path": str(model),
        "layout_model_path": str(layout),
        "vlm_device": "GPU",
        "layout_device": "CPU",
        "llm_int4_compress": True,
        "vision_int8_quant": True,
    }
    assert predicted == {
        "inputs": [str(page.image_path) for page in pages],
        "vlm_batch_size": 32,
        "max_new_tokens": 64,
    }
    assert [result.text for result in results] == ["raw 1", "raw 2"]


def test_adapter_rejects_non_text_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeResult:
        def __init__(self) -> None:
            self.markdown = {"markdown_texts": 123}

    class FakePaddleOCRVL:
        def __init__(self, **_: object) -> None:
            return None

        def predict(self, *_: object, **__: object) -> list[FakeResult]:
            return [FakeResult()]

    package = ModuleType("paddleocr_vl_openvino")
    pipeline_module = ModuleType(
        "paddleocr_vl_openvino.paddleocr_vl_pipeline"
    )
    pipeline_module.PaddleOCRVL = FakePaddleOCRVL
    monkeypatch.setitem(sys.modules, "paddleocr_vl_openvino", package)
    monkeypatch.setitem(
        sys.modules,
        "paddleocr_vl_openvino.paddleocr_vl_pipeline",
        pipeline_module,
    )
    page = SourcePage(PageNumber(1), tmp_path / "1.jpg")

    with pytest.raises(RuntimeError, match="non-text Markdown"):
        tuple(
            OpenVinoPaddleRecognizerAdapter(
                OpenVinoBackendConfig(tmp_path)
            ).recognize_many((page,))
        )
