"""Format-neutral document output contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from domain.content import DocumentBundle
from domain.status import ProcessingStatus


@dataclass(frozen=True, slots=True)
class OutputResult:
    """Files created by one document output operation."""

    files: tuple[Path, ...]


class DocumentOutputPort(Protocol):
    """Persist a format-neutral bundle and its processing status."""

    def write(
        self,
        bundle: DocumentBundle,
        status: ProcessingStatus,
    ) -> OutputResult:
        """Write output artifacts and return their paths."""
        ...
