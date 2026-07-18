"""Document grouping use case."""

from application.policies.group.base import GroupingPolicy
from domain.content import DocumentBundle, PageContent


def group_pages(
    policy: GroupingPolicy,
    pages: tuple[PageContent, ...],
) -> DocumentBundle:
    """Apply the selected output grouping policy."""
    return policy.group(pages)
