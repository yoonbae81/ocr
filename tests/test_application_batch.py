from collections.abc import Iterator
from pathlib import Path

from application import export_cached_pages, export_recognized_pages
from domain import PageMarkdown, PageNumber, SourcePage


class FakeCache:
    def __init__(self, cached: dict[int, str]) -> None:
        self._cached = cached
        self.stored: list[int] = []

    def load(self, page: SourcePage) -> PageMarkdown | None:
        text = self._cached.get(page.number.value)
        return PageMarkdown(page, text) if text is not None else None

    def store(self, result: PageMarkdown) -> None:
        self.stored.append(result.page.number.value)


class FakeExporter:
    def __init__(self) -> None:
        self.exported: list[tuple[int, str]] = []

    def is_exported(self, page: PageNumber, destination: Path) -> bool:
        del page, destination
        return False

    def export(self, result: PageMarkdown, destination: Path, replace: bool) -> None:
        del destination, replace
        self.exported.append((result.page.number.value, result.text))


class FakeBatchRecognizer:
    def __init__(self) -> None:
        self.batches: list[tuple[int, ...]] = []

    def recognize_many(
        self, pages: tuple[SourcePage, ...]
    ) -> Iterator[PageMarkdown]:
        self.batches.append(tuple(page.number.value for page in pages))
        for page in pages:
            yield PageMarkdown(page, f"raw {page.number.value}")


def test_export_cached_pages_returns_only_cache_misses(tmp_path: Path) -> None:
    expected_exported = 2
    pages = tuple(
        SourcePage(PageNumber(number), tmp_path / f"{number}.jpg")
        for number in range(1, 4)
    )
    exporter = FakeExporter()

    missing, exported = export_cached_pages(
        pages,
        FakeCache({1: "cached 1", 3: "cached 3"}),
        exporter,
        tmp_path / "book",
        replace=True,
    )

    assert missing == (pages[1],)
    assert exported == expected_exported
    assert exporter.exported == [(1, "cached 1"), (3, "cached 3")]


def test_export_recognized_pages_uses_bounded_batches(tmp_path: Path) -> None:
    expected_exported = 5
    pages = tuple(
        SourcePage(PageNumber(number), tmp_path / f"{number}.jpg")
        for number in range(1, 6)
    )
    recognizer = FakeBatchRecognizer()
    exporter = FakeExporter()
    cache = FakeCache({})

    exported = export_recognized_pages(
        pages,
        recognizer,
        exporter,
        cache,
        tmp_path / "book",
        replace=False,
        batch_size=2,
    )

    assert exported == expected_exported
    assert recognizer.batches == [(1, 2), (3, 4), (5,)]
    assert cache.stored == [1, 2, 3, 4, 5]
    assert exporter.exported == [
        (1, "raw 1"),
        (2, "raw 2"),
        (3, "raw 3"),
        (4, "raw 4"),
        (5, "raw 5"),
    ]
