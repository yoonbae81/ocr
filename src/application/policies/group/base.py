"""Grouping policy contract."""

from typing import Protocol

from domain.content import DocumentBundle, PageContent


class GroupingPolicy(Protocol):
    """Arrange structured page content into output document groups."""

    def group(self, pages: tuple[PageContent, ...]) -> DocumentBundle:
        """Create a format-neutral document bundle."""
        ...
