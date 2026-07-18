"""Page acquisition contract."""

from typing import Protocol

from domain.content import PageNumber, SourcePage
from domain.document import Document


class PageSourcePort(Protocol):
    """Acquire selected pages from a document."""

    def read(
        self,
        document: Document,
        pages: tuple[PageNumber, ...],
    ) -> tuple[SourcePage, ...]:
        """Return pages in the requested order."""
        ...
