"""One output group for the selected document."""

from domain.content import DocumentBundle, DocumentGroup, PageContent


class BookGroupPolicy:
    """Keep the selected pages in one format-neutral document group."""

    def group(self, pages: tuple[PageContent, ...]) -> DocumentBundle:
        """Create one book group without rendering or parsing Markdown."""
        return DocumentBundle(groups=(DocumentGroup(name="book", pages=pages),))
