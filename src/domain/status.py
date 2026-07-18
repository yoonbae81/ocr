"""Immutable OCR processing state."""

from dataclasses import dataclass

from domain.content import PageNumber


@dataclass(frozen=True, slots=True)
class PageFailure:
    """One page that could not be processed."""

    page: PageNumber
    reason: str


@dataclass(frozen=True, slots=True)
class ProcessingStatus:
    """Completed and failed pages available to a resumed run."""

    document: str | None = None
    completed: tuple[PageNumber, ...] = ()
    failures: tuple[PageFailure, ...] = ()
    current_chapter: str | None = None
