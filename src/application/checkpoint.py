"""Processing-status transitions."""

from domain.content import PageContent, PageNumber
from domain.status import PageFailure, ProcessingStatus


def merge_status(
    previous: ProcessingStatus,
    content: tuple[PageContent, ...],
    failures: tuple[PageFailure, ...],
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
    )
