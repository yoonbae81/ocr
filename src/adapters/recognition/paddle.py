"""PaddleOCR-VL pipeline adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from math import sqrt
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from PIL import Image, UnidentifiedImageError

from domain.content import ImagePage

if TYPE_CHECKING:
    from collections.abc import Sequence

from ._cli import temporary_image
from .errors import RecognitionError

PADDLE_MIN_PIXELS = 28 * 28 * 130
PADDLE_MAX_PIXELS = 28 * 28 * 2048
PADDLE_TEMPERATURE = 0.0
PADDLE_MAX_NEW_TOKENS = 4096


class PaddleResult(Protocol):
    """Subset of a PaddleOCR-VL result used by the application."""

    def save_to_markdown(self, save_path: str, *, pretty: bool) -> None:
        """Save converted Markdown using the requested formatting mode."""
        ...


@runtime_checkable
class PaddlePipeline(Protocol):
    """Subset of the PaddleOCR-VL pipeline used by the adapter."""

    def predict(
        self,
        input_path: str,
        *,
        temperature: float,
        max_new_tokens: int,
        **kwargs: object,
    ) -> Sequence[PaddleResult]:
        """Run document layout analysis and VLM recognition for one image."""
        ...


@runtime_checkable
class _ImageWithSize(Protocol):
    @property
    def size(self) -> tuple[int, int]: ...


def _create_paddle_pipeline(endpoint: str, model: str) -> object:
    from paddleocr import PaddleOCRVL  # noqa: PLC0415

    return PaddleOCRVL(
        pipeline_version="v1.6",
        vl_rec_backend="mlx-vlm-server",
        vl_rec_server_url=endpoint,
        vl_rec_api_model_name=model,
    )


def _build_pipeline(endpoint: str, model: str) -> PaddlePipeline:
    pipeline = _create_paddle_pipeline(endpoint, model)
    if not isinstance(pipeline, PaddlePipeline):
        raise RecognitionError(detail="PaddleOCR-VL pipeline has no predict method")
    return pipeline


def _image_dimensions(image: object) -> tuple[int, int]:
    if not isinstance(image, _ImageWithSize):
        raise RecognitionError(detail="Pillow image has invalid dimensions")
    return image.size


def _smart_resize(page: ImagePage) -> ImagePage:
    try:
        image = Image.open(BytesIO(page.image))
    except UnidentifiedImageError:
        return page

    width, height = _image_dimensions(image)
    pixels = width * height
    scale: float = 1.0
    if pixels < PADDLE_MIN_PIXELS:
        scale = sqrt(PADDLE_MIN_PIXELS / pixels)
    elif pixels > PADDLE_MAX_PIXELS:
        scale = sqrt(PADDLE_MAX_PIXELS / pixels)
    resized_width = max(28, round(width * scale / 28) * 28)
    resized_height = max(28, round(height * scale / 28) * 28)
    if (resized_width, resized_height) == (width, height):
        return page

    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    output = BytesIO()
    format_name = "JPEG" if page.media_type == "image/jpeg" else "PNG"
    resized.save(output, format=format_name)
    return ImagePage(
        page=page.page,
        image=output.getvalue(),
        media_type=page.media_type,
        source=page.source,
    )


@dataclass(slots=True)
class PaddleAdapter:
    """Recognize page images through the configured PaddleOCR-VL service."""

    endpoint: str
    model: str
    pipeline: PaddlePipeline | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Build the pipeline once unless a test or caller supplies one."""
        if self.pipeline is None:
            self.pipeline = _build_pipeline(self.endpoint, self.model)

    def recognize(self, page: ImagePage, prompt: str) -> str:
        """Return the first page result as Markdown."""
        _ = prompt
        if self.pipeline is None:
            raise RecognitionError(detail="PaddleOCR-VL pipeline is not initialized")
        resized_page = _smart_resize(page)
        with temporary_image(resized_page) as image_path:
            try:
                results = self.pipeline.predict(
                    image_path.as_posix(),
                    temperature=PADDLE_TEMPERATURE,
                    max_new_tokens=PADDLE_MAX_NEW_TOKENS,
                    use_chart_recognition=True,
                    use_ocr_for_image_block=True,
                    markdown_ignore_labels=[],
                    vlm_extra_args={
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
                )
            except (OSError, RuntimeError, ValueError) as error:
                raise RecognitionError(detail="PaddleOCR-VL request failed") from error
        if not results:
            raise RecognitionError(detail="PaddleOCR-VL returned no result")
        with TemporaryDirectory(prefix="paddle-markdown-") as directory:
            markdown_path = Path(directory) / "result.md"
            try:
                results[0].save_to_markdown(markdown_path.as_posix(), pretty=False)
                markdown = markdown_path.read_text(encoding="utf-8").strip()
            except (OSError, RuntimeError, ValueError) as error:
                raise RecognitionError(
                    detail="PaddleOCR-VL result conversion failed"
                ) from error
            if not markdown:
                raise RecognitionError(detail="PaddleOCR-VL returned empty content")
            return markdown
