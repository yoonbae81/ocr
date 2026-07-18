"""Chapter boundaries resolved from a document outline or contents page."""

from dataclasses import dataclass

from domain.content import PageNumber


@dataclass(frozen=True, slots=True)
class PartBoundary:
    """The first PDF page belonging to one named part."""

    page: PageNumber
    title: str


@dataclass(frozen=True, slots=True)
class ChapterBoundary:
    """The first PDF page belonging to one named chapter."""

    page: PageNumber
    title: str
    part: str | None = None


@dataclass(frozen=True, slots=True)
class ChapterMap:
    """Ordered chapter boundaries for one PDF document."""

    boundaries: tuple[ChapterBoundary, ...]
    parts: tuple[PartBoundary, ...] = ()

    def chapter_for(self, page: PageNumber) -> str | None:
        """Return the chapter containing a PDF page, when one is known."""
        boundary = self.boundary_for(page)
        return boundary.title if boundary is not None else None

    def boundary_for(self, page: PageNumber) -> ChapterBoundary | None:
        """Return the chapter boundary containing a PDF page, when one is known."""
        chapter: ChapterBoundary | None = None
        for boundary in self.boundaries:
            if boundary.page > page:
                break
            chapter = boundary
        return chapter
