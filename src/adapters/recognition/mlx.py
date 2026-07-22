"""PaddleOCR-VL recognition adapter backed by an MLX-VLM service."""

from __future__ import annotations

from collections.abc import Iterator

from domain import PageMarkdown, SourcePage


class MlxPaddleRecognizerAdapter:
    """Keep one PaddleOCR-VL client pipeline alive for the command."""

    def __init__(
        self,
        server_url: str,
        model_name: str,
        max_concurrency: int | None = None,
    ) -> None:
        from paddleocr import PaddleOCRVL  # pyright: ignore[reportMissingImports]

        options: dict[str, str | int] = {
            "vl_rec_backend": "mlx-vlm-server",
            "vl_rec_server_url": server_url,
            "vl_rec_api_model_name": model_name,
        }
        if max_concurrency is not None:
            options["vl_rec_max_concurrency"] = max_concurrency
        self._pipeline = PaddleOCRVL(**options)

    def recognize_many(
        self, pages: tuple[SourcePage, ...]
    ) -> Iterator[PageMarkdown]:
        """Run one Paddle queue pipeline for a bounded page batch."""
        inputs = [str(page.image_path) for page in pages]
        results = self._pipeline.predict_iter(inputs)
        for page, result in zip(pages, results, strict=True):
            text = result.markdown["markdown_texts"]
            if not isinstance(text, str):
                raise RuntimeError("PaddleOCR-VL returned non-text Markdown output.")
            yield PageMarkdown(page, text)
