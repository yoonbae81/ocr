"""PaddleOCR-VL recognition adapter backed directly by OpenVINO."""

from __future__ import annotations

from collections.abc import Iterator

from backend_config import OpenVinoBackendConfig
from domain import PageMarkdown, SourcePage


class OpenVinoPaddleRecognizerAdapter:
    """Keep one in-process OpenVINO document pipeline alive for the command."""

    def __init__(self, config: OpenVinoBackendConfig) -> None:
        try:
            from paddleocr_vl_openvino.paddleocr_vl_pipeline import (  # pyright: ignore[reportMissingImports]
                PaddleOCRVL,
            )
        except ImportError as error:
            raise RuntimeError(
                "OpenVINO backend dependencies are not installed; "
                "install the project with the 'openvino' extra."
            ) from error

        options: dict[str, object] = {
            "vlm_model_path": str(config.vlm_model_path),
            "layout_model_path": (
                None
                if config.layout_model_path is None
                else str(config.layout_model_path)
            ),
            "vlm_device": config.vlm_device,
            "layout_device": config.layout_device,
            "llm_int4_compress": config.llm_int4_compress,
            "vision_int8_quant": config.vision_int8_quant,
        }
        if config.model_cache_dir is not None:
            options["cache_dir"] = str(config.model_cache_dir)
        self._pipeline = PaddleOCRVL(**options)
        self._vlm_batch_size = config.vlm_batch_size
        self._max_new_tokens = config.max_new_tokens

    def recognize_many(
        self, pages: tuple[SourcePage, ...]
    ) -> Iterator[PageMarkdown]:
        """Recognize pages in one call while preserving input order."""
        inputs = [str(page.image_path) for page in pages]
        results = self._pipeline.predict(
            inputs,
            vlm_batch_size=self._vlm_batch_size,
            max_new_tokens=self._max_new_tokens,
        )
        for page, result in zip(pages, results, strict=True):
            text = result.markdown["markdown_texts"]
            if not isinstance(text, str):
                raise RuntimeError("PaddleOCR-VL returned non-text Markdown output.")
            yield PageMarkdown(page, text)
