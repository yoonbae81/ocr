"""Use case that connects source, recognition, and output ports."""

from __future__ import annotations

from itertools import batched
from pathlib import Path

from domain import PageNumber, SourcePage
from ports import PageRecognizer, PageSource
from ports.cache import RecognitionCache
from ports.output import PageExporter


def select_export_pages(
    source: PageSource,
    exporter: PageExporter,
    destination: Path,
    selection: tuple[PageNumber, ...] | None,
    replace: bool,
    resume: bool,
) -> tuple[SourcePage, ...]:
    """Select rendered pages that require recognition before starting the backend."""
    selected: list[SourcePage] = []
    for page in source.pages(selection):
        if not exporter.is_exported(page.number, destination) or replace:
            selected.append(page)
        elif not resume:
            raise FileExistsError(
                f"Page {page.number.value} exists; pass --replace or --resume."
            )
    return tuple(selected)


def export_cached_pages(
    pages: tuple[SourcePage, ...],
    cache: RecognitionCache,
    exporter: PageExporter,
    destination: Path,
    replace: bool,
) -> tuple[tuple[SourcePage, ...], int]:
    """Export cache hits and return only pages that still require recognition."""
    missing: list[SourcePage] = []
    exported = 0
    for page in pages:
        cached = cache.load(page)
        if cached is None:
            missing.append(page)
        else:
            exporter.export(cached, destination, replace)
            exported += 1
    return tuple(missing), exported


def export_recognized_pages(
    pages: tuple[SourcePage, ...],
    recognizer: PageRecognizer,
    exporter: PageExporter,
    cache: RecognitionCache,
    destination: Path,
    replace: bool,
    batch_size: int,
) -> int:
    """Recognize cache misses in bounded batches, cache them, and export them."""
    exported = 0
    for page_batch in batched(pages, batch_size, strict=False):
        for result in recognizer.recognize_many(page_batch):
            cache.store(result)
            exporter.export(result, destination, replace)
            exported += 1
    return exported
