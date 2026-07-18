"""Checkpoint batching and processing-status transitions."""

from enum import StrEnum

from domain.chapters import ChapterMap
from domain.content import DocumentBundle, PageContent, PageNumber, SourcePage
from domain.status import PageFailure, ProcessingStatus


class GroupName(StrEnum):
    """Output grouping policies selectable from the terminal."""

    PAGE = "page"
    CHAPTER = "chapter"
    BOOK = "book"


def checkpoint_batches(
    pages: tuple[SourcePage, ...],
    group: GroupName,
    chapter_map: ChapterMap | None,
) -> tuple[tuple[SourcePage, ...], ...]:
    """Split chapter-mode work so each completed chapter can be persisted."""
    if group is not GroupName.CHAPTER or chapter_map is None:
        return (pages,)

    batches: list[list[SourcePage]] = []
    current_key: tuple[str, str | None] | None = None
    for page in pages:
        boundary = chapter_map.boundary_for(page.page)
        key = (
            (boundary.title, boundary.part)
            if boundary is not None
            else ("frontmatter", None)
        )
        if batches and key != current_key:
            batches.append([])
        if not batches:
            batches.append([])
        batches[-1].append(page)
        current_key = key
    return tuple(tuple(batch) for batch in batches)


def merge_status(
    previous: ProcessingStatus,
    content: tuple[PageContent, ...],
    failures: tuple[PageFailure, ...],
    current_chapter: str | None,
    *,
    document: str,
) -> ProcessingStatus:
    """Merge one attempted batch into the persisted processing status."""
    completed_pages = frozenset(page.page for page in content)
    attempted_pages = completed_pages | frozenset(failure.page for failure in failures)
    completed = tuple(
        PageNumber(page)
        for page in sorted(frozenset(previous.completed) | completed_pages)
    )
    retained_failures = (
        failure
        for failure in previous.failures
        if failure.page not in attempted_pages and failure.page not in completed_pages
    )
    current_failures = (
        failure for failure in failures if failure.page not in completed_pages
    )
    merged_failures = tuple(
        sorted(
            (*retained_failures, *current_failures),
            key=lambda failure: failure.page,
        )
    )
    return ProcessingStatus(
        document=document,
        completed=completed,
        failures=merged_failures,
        current_chapter=current_chapter,
    )


def current_chapter(
    group: GroupName,
    bundle: DocumentBundle,
    previous: ProcessingStatus,
) -> str | None:
    """Return the latest persisted chapter after one grouped batch."""
    match group:
        case GroupName.CHAPTER if bundle.groups:
            return bundle.groups[-1].name
        case GroupName.CHAPTER | GroupName.PAGE | GroupName.BOOK:
            return previous.current_chapter
