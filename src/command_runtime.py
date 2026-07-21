"""Per-source OCR execution used by the command-line boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import typer

from adapters.cache.disabled import DisabledRecognitionCache
from adapters.cache.filesystem import FilesystemRecognitionCache
from adapters.output.markdown import MarkdownPageExporter
from application import (
    select_export_pages,
)
from domain import PageNumber, SourcePage
from ports import PageRecognizer, PageSource
from source_adapter import ImageSourceAdapter, PdfSourceAdapter, ZipSourceAdapter


MODEL = "matrixmaven/PaddleOCR-VL-1.6-MLX"


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Immutable options shared by every source in one command."""

    pages: tuple[PageNumber, ...] | None
    dpi: int
    zip_filename_prefix: str | None
    replace: bool
    resume: bool
    batch_size: int
    use_cache: bool
    cache_dir: Path | None
    profile: bool


RecognizerFactory = Callable[[], PageRecognizer]


def _source_adapter(
    source: Path, dpi: int, temporary: Path, zip_filename_prefix: str | None
) -> PageSource:
    match source.suffix.lower():
        case ".pdf":
            return PdfSourceAdapter(source, dpi, temporary)
        case ".jpg" | ".jpeg" | ".png" | ".webp":
            return ImageSourceAdapter(source, temporary)
        case ".zip":
            return ZipSourceAdapter(source, temporary, zip_filename_prefix)
        case suffix:
            raise typer.BadParameter(f"Unsupported source type: {suffix}")


def _page_range_label(pages: tuple[int, ...]) -> str:
    if not pages:
        return "no pages"
    first = pages[0]
    last = pages[-1]
    if first == last:
        return str(first)
    return f"{first}-{last}"


def run_source(
    source: Path,
    options: RunOptions,
    recognizer: RecognizerFactory,
) -> int:
    """Process one source while reusing the command-owned recognizer."""
    destination = Path.cwd() / source.stem
    started = perf_counter()
    prepare_seconds = 0.0
    cache_seconds = 0.0
    recognition_seconds = 0.0
    cached = 0
    recognized = 0
    with TemporaryDirectory(prefix="ocr-") as temporary:
        typer.echo(f"[{source.name}] Created temporary workspace at {temporary}.")
        source_adapter = _source_adapter(
            source,
            options.dpi,
            Path(temporary),
            options.zip_filename_prefix,
        )
        typer.echo(f"[{source.name}] Converting input to pages (dpi={options.dpi})")
        exporter = MarkdownPageExporter()
        if options.use_cache:
            cache_root = options.cache_dir or Path.home() / ".cache" / "ocr" / "raw"
            cache = FilesystemRecognitionCache(cache_root, MODEL)
            typer.echo(
                f"[{source.name}] Cache enabled: {cache_root / MODEL}"
            )
        else:
            cache = DisabledRecognitionCache()
            typer.echo(f"[{source.name}] Cache disabled")

        for page_numbers in (
            (None,)
            if options.pages is None
            else batched(options.pages, options.batch_size, strict=False)
        ):
            phase_started = perf_counter()
            selected = select_export_pages(
                source_adapter,
                exporter,
                destination,
                page_numbers,
                options.replace,
                options.resume,
            )
            prepare_seconds += perf_counter() - phase_started

            page_results: list[SourcePage] = []
            for page in selected:
                page_started = perf_counter()
                cached_content = cache.load(page)
                if cached_content is None:
                    page_results.append(page)
                    continue
                exporter.export(cached_content, destination, options.replace)
                cached += 1
                cache_seconds += perf_counter() - page_started

            for page_batch in batched(page_results, options.batch_size, strict=False):
                batch_started = perf_counter()
                results = tuple(recognizer().recognize_many(page_batch))
                batch_elapsed = perf_counter() - batch_started
                if not results:
                    continue
                page_numbers = tuple(result.page.number.value for result in results)
                recognition_seconds += batch_elapsed
                for result in results:
                    cache.store(result)
                    exporter.export(result, destination, options.replace)
                    recognized += 1
                typer.echo(
                    f"[{source.name}] Recognized {_page_range_label(page_numbers)} "
                    f"({len(page_numbers)} page(s)) in {batch_elapsed:.3f}s, "
                    f"avg {batch_elapsed / len(page_numbers):.3f}s/page"
                )
        exported = cached + recognized
    total_seconds = perf_counter() - started
    if options.profile:
        typer.echo(
            f"Timing ({source.name}): "
            f"prepare={prepare_seconds:.3f}s "
            f"cache={cache_seconds:.3f}s "
            f"recognition={recognition_seconds:.3f}s "
            f"total={total_seconds:.3f}s "
            f"cache_hits={cached}"
        )
    typer.echo(f"Exported {exported} page(s) to {destination}")
    return exported
