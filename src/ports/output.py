"""Output boundary for publishing recognized document pages."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from domain import PageMarkdown, PageNumber


class PageExporter(Protocol):
    """Publishes recognized pages in a chosen output format."""

    def is_exported(self, page: PageNumber, destination: Path) -> bool:
        """Return whether the page already exists in this output format."""
        ...

    def export(self, result: PageMarkdown, destination: Path, replace: bool) -> None:
        """Write one recognized page to the chosen output representation."""
        ...
