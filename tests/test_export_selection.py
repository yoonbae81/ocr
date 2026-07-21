from collections.abc import Iterator
from pathlib import Path

import pytest

from application import select_export_pages
from domain import PageMarkdown, PageNumber, SourcePage


class FakePageSource:
    def __init__(self, pages: tuple[SourcePage, ...]) -> None:
        self._pages = pages

    def pages(self, selection: tuple[PageNumber, ...] | None) -> Iterator[SourcePage]:
        del selection
        yield from self._pages


class FakePageExporter:
    def __init__(self, exported: set[int]) -> None:
        self._exported = exported

    def is_exported(self, page: PageNumber, destination: Path) -> bool:
        del destination
        return page.value in self._exported

    def export(self, result: PageMarkdown, destination: Path, replace: bool) -> None:
        del result, destination, replace


def test_select_export_pages_skips_existing_pages_when_resuming(tmp_path: Path) -> None:
    pages = (
        SourcePage(PageNumber(1), tmp_path / "1.jpg"),
        SourcePage(PageNumber(2), tmp_path / "2.jpg"),
    )

    selected = select_export_pages(
        FakePageSource(pages),
        FakePageExporter({1}),
        tmp_path / "book",
        None,
        replace=False,
        resume=True,
    )

    assert selected == (pages[1],)


def test_select_export_pages_rejects_existing_page_before_recognition(
    tmp_path: Path,
) -> None:
    page = SourcePage(PageNumber(1), tmp_path / "1.jpg")

    with pytest.raises(FileExistsError, match="--replace or --resume"):
        select_export_pages(
            FakePageSource((page,)),
            FakePageExporter({1}),
            tmp_path / "book",
            None,
            replace=False,
            resume=False,
        )
