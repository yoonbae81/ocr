"""Ports for document input source iteration."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from domain import PageNumber, SourcePage


class PageSource(Protocol):
    """Supplies selected rendered pages from an input document."""

    def pages(self, selection: tuple[PageNumber, ...] | None) -> Iterator[SourcePage]:
        """Yield source pages in physical-page order."""
        ...
