"""Page acquisition use case."""

from application.ports.source import PageSourcePort
from domain.content import PageNumber, SourcePage
from domain.document import Document


def acquire_pages(
    source: PageSourcePort,
    document: Document,
    pages: tuple[PageNumber, ...],
) -> tuple[SourcePage, ...]:
    """Acquire the selected source pages in document order."""
    return source.read(document, pages)
