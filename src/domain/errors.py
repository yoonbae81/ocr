"""Typed domain errors."""

from dataclasses import dataclass
from pathlib import Path
from typing import override

from domain.content import PageNumber


@dataclass(slots=True)
class UnsupportedDocumentError(Exception):
    """Raised when an input file type is outside the OCR boundary."""

    path: Path

    @override
    def __str__(self) -> str:
        """Describe the unsupported input path."""
        return f"unsupported input document: {self.path}"


@dataclass(slots=True)
class PageNotAvailableError(Exception):
    """Raised when a selected page is absent from the source."""

    page: PageNumber

    @override
    def __str__(self) -> str:
        """Describe the unavailable page."""
        return f"page {self.page} is not available"


@dataclass(frozen=True, slots=True)
class ImageSizeLimitError(ValueError):
    """Raised when one source image exceeds the configured safety limit."""

    path: Path
    limit: int

    @override
    def __str__(self) -> str:
        return f"image exceeds {self.limit} byte limit: {self.path}"


@dataclass(frozen=True, slots=True)
class ArchiveSizeLimitError(ValueError):
    """Raised when a ZIP contains too many entries."""

    limit: int

    @override
    def __str__(self) -> str:
        return f"ZIP archive exceeds {self.limit} entry limit"


@dataclass(frozen=True, slots=True)
class ArchiveImageSizeLimitError(ValueError):
    """Raised when one ZIP image exceeds the configured safety limit."""

    name: str
    limit: int

    @override
    def __str__(self) -> str:
        return f"ZIP image exceeds {self.limit} byte limit: {self.name}"


@dataclass(frozen=True, slots=True)
class UnsafeOutputPathError(ValueError):
    """Raised when output would traverse a symbolic link."""

    path: Path

    @override
    def __str__(self) -> str:
        return f"output path must not contain symlinks: {self.path}"
