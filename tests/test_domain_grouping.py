from application.policies.group.book import BookGroupPolicy
from application.policies.group.chapter import ChapterGroupPolicy
from application.policies.group.page import PageGroupPolicy
from domain.chapters import ChapterBoundary, ChapterMap
from domain.content import PageContent, PageNumber


def test_page_grouping_when_pages_are_transcribed_creates_one_group_per_page() -> None:
    # Given: two independently transcribed pages.
    pages = (
        PageContent(page=PageNumber(1), body="first"),
        PageContent(page=PageNumber(2), body="second"),
    )

    # When: page grouping is selected.
    bundle = PageGroupPolicy().group(pages)

    # Then: each page remains a separately renderable document group.
    assert tuple(group.name for group in bundle.groups) == ("1", "2")
    assert tuple(group.pages for group in bundle.groups) == ((pages[0],), (pages[1],))


def test_chapter_grouping_when_adjacent_pages_share_a_chapter_groups_them() -> None:
    pages = (
        PageContent(page=PageNumber(1), body="one"),
        PageContent(page=PageNumber(2), body="two"),
        PageContent(page=PageNumber(3), body="three"),
    )

    bundle = ChapterGroupPolicy(
        chapter_map=ChapterMap(
            boundaries=(
                ChapterBoundary(page=PageNumber(1), title="intro", part="book one"),
                ChapterBoundary(page=PageNumber(3), title="methods", part="book two"),
            )
        )
    ).group(pages)

    assert tuple(group.name for group in bundle.groups) == ("intro", "methods")
    assert tuple(group.parent for group in bundle.groups) == ("book one", "book two")
    assert tuple(group.pages for group in bundle.groups) == (
        (pages[0], pages[1]),
        (pages[2],),
    )


def test_chapter_grouping_when_contents_map_has_korean_chapters_uses_boundaries() -> (
    None
):
    # Given: a bookmarkless document with boundaries resolved from its contents page.
    pages = (
        PageContent(page=PageNumber(1), body="표지"),
        PageContent(page=PageNumber(2), body="시작"),
        PageContent(page=PageNumber(3), body="첫 장의 계속"),
        PageContent(page=PageNumber(4), body="다음 내용"),
        PageContent(page=PageNumber(5), body="둘째 장의 계속"),
    )

    # When: chapter grouping receives the resolved contents map.
    bundle = ChapterGroupPolicy(
        chapter_map=ChapterMap(
            boundaries=(
                ChapterBoundary(page=PageNumber(2), title="제 1 장"),
                ChapterBoundary(page=PageNumber(4), title="2장"),
            )
        )
    ).group(pages)

    # Then: leading pages remain in front matter until a heading begins a chapter.
    assert tuple(group.name for group in bundle.groups) == (
        "frontmatter",
        "제 1 장",
        "2장",
    )
    assert tuple(group.pages for group in bundle.groups) == (
        (pages[0],),
        (pages[1], pages[2]),
        (pages[3], pages[4]),
    )


def test_chapter_grouping_when_contents_map_has_english_chapter_keeps_title() -> None:
    # Given: a bookmarkless document with an English contents entry.
    pages = (
        PageContent(page=PageNumber(1), body="Introduction"),
        PageContent(page=PageNumber(2), body="Continuation"),
    )

    # When: chapter grouping receives the resolved contents map.
    bundle = ChapterGroupPolicy(
        chapter_map=ChapterMap(
            boundaries=(ChapterBoundary(page=PageNumber(1), title="Chapter 1"),)
        )
    ).group(pages)

    # Then: the case-preserved heading is the group name.
    assert tuple(group.name for group in bundle.groups) == ("Chapter 1",)
    assert bundle.groups[0].pages == pages


def test_chapter_grouping_when_page_metadata_conflicts_prefers_toc() -> None:
    pages = (
        PageContent(
            page=PageNumber(1),
            body="Chapter 99\nIncorrect OCR text",
            chapter="source chapter",
        ),
        PageContent(page=PageNumber(2), body="Continuation"),
    )

    bundle = ChapterGroupPolicy(
        chapter_map=ChapterMap(
            boundaries=(ChapterBoundary(page=PageNumber(1), title="TOC chapter"),)
        )
    ).group(pages)

    assert tuple(group.name for group in bundle.groups) == ("TOC chapter",)
    assert bundle.groups[0].pages == pages


def test_book_grouping_when_pages_are_transcribed_creates_one_document_group() -> None:
    # Given: a selected range from one document.
    pages = (
        PageContent(page=PageNumber(5), body="five"),
        PageContent(page=PageNumber(6), body="six"),
    )

    # When: book grouping is selected.
    bundle = BookGroupPolicy().group(pages)

    # Then: no Markdown is parsed or combined by the policy.
    assert tuple(group.name for group in bundle.groups) == ("book",)
    assert bundle.groups[0].pages == pages
