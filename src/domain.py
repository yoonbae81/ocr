"""Stable domain values for the OCR export flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PageNumber:
    """A one-based physical page number."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("Page numbers start at 1.")


@dataclass(frozen=True, slots=True)
class SourcePage:
    """One rendered source page held in the command's temporary workspace."""

    number: PageNumber
    image_path: Path


@dataclass(frozen=True, slots=True)
class PageMarkdown:
    """Markdown returned by document recognition for one source page."""

    page: SourcePage
    text: str
