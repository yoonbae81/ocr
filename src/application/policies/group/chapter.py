"""One output group per source chapter."""

from dataclasses import dataclass
from typing import Final

from application.toc import ChapterMapUnavailableError
from domain.chapters import ChapterMap
from domain.content import DocumentBundle, DocumentGroup, PageContent

_FRONT_MATTER: Final = "frontmatter"
type _GroupKey = tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class ChapterGroupPolicy:
    """Group pages by source metadata or an already-resolved contents map."""

    current_chapter: str | None = None
    chapter_map: ChapterMap | None = None

    def group(self, pages: tuple[PageContent, ...]) -> DocumentBundle:
        """Create ordered chapter groups without rendering their bodies."""
        names: list[_GroupKey] = []
        grouped: dict[_GroupKey, list[PageContent]] = {}
        current_chapter = (
            (self.current_chapter, None) if self.current_chapter is not None else None
        )
        for page in pages:
            current_chapter = _mapped_chapter(self.chapter_map, page) or current_chapter
            if current_chapter is None:
                raise ChapterMapUnavailableError
            if current_chapter not in grouped:
                names.append(current_chapter)
                grouped[current_chapter] = []
            grouped[current_chapter].append(page)
        return DocumentBundle(
            groups=tuple(
                DocumentGroup(
                    name=name,
                    parent=parent,
                    pages=tuple(grouped[name, parent]),
                )
                for name, parent in names
            )
        )


def _mapped_chapter(
    chapter_map: ChapterMap | None, page: PageContent
) -> _GroupKey | None:
    if chapter_map is None:
        return None
    boundary = chapter_map.boundary_for(page.page)
    if boundary is None:
        return (_FRONT_MATTER, None)
    return (boundary.title, boundary.part)
