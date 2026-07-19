"""Page Markdown output contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from domain.content import PageContent
from domain.status import ProcessingStatus


@dataclass(frozen=True, slots=True)
class OutputResult:
    """Files created by one document output operation."""

    files: tuple[Path, ...]


class DocumentOutputPort(Protocol):
    """Persist page artifacts and their processing status."""

    def write(
        self,
        pages: tuple[PageContent, ...],
        status: ProcessingStatus,
        *,
        source_name: str,
    ) -> OutputResult:
        """Write output artifacts and return their paths."""
        ...
