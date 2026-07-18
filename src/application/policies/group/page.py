"""One output group per page."""

from domain.content import DocumentBundle, DocumentGroup, PageContent


class PageGroupPolicy:
    """Keep each page as its own output artifact."""

    def group(self, pages: tuple[PageContent, ...]) -> DocumentBundle:
        """Create ordered page groups without rendering their bodies."""
        return DocumentBundle(
            groups=tuple(
                DocumentGroup(name=str(page.page), pages=(page,)) for page in pages
            )
        )
