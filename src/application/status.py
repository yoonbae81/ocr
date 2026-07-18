"""Resume state use case."""

from domain.content import PageNumber
from domain.status import ProcessingStatus


def pending_pages(
    selected: tuple[PageNumber, ...],
    status: ProcessingStatus,
    *,
    retry_failed: bool,
) -> tuple[PageNumber, ...]:
    """Return selected pages according to the explicit resume policy."""
    completed = frozenset(status.completed)
    failed = frozenset(failure.page for failure in status.failures)
    if retry_failed:
        return tuple(page for page in selected if page in failed)
    return tuple(
        page for page in selected if page not in completed and page not in failed
    )
