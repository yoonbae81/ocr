from pathlib import Path

import pytest

from application.toc import ChapterMapUnavailableError, load_chapter_map
from domain.content import PageNumber


def test_load_chapter_map_when_toc_has_chapters_parses_physical_pages(
    tmp_path: Path,
) -> None:
    toc = tmp_path / "toc.md"
    _ = toc.write_text(
        chr(10).join(
            [
                "# Table of Contents",
                "",
                "## 첫째 권 | page: 1",
                "",
                "### 제1장 기초 | page: 12",
                "",
                "- page: 12",
                "  title: 첫 번째 세부 항목",
                "",
                "### 제2장 응용 | page: 38",
                "",
                "- page: 38",
                "  title: 두 번째 세부 항목",
            ]
        ),
        encoding="utf-8",
    )

    chapter_map = load_chapter_map(toc)

    assert chapter_map.chapter_for(PageNumber(12)) == "제1장 기초"
    assert chapter_map.chapter_for(PageNumber(37)) == "제1장 기초"
    assert chapter_map.chapter_for(PageNumber(38)) == "제2장 응용"
    assert chapter_map.boundaries[0].page == PageNumber(12)
    assert chapter_map.boundaries[0].part == "첫째 권"
    assert chapter_map.parts[0].page == PageNumber(1)
    assert chapter_map.parts[0].title == "첫째 권"


def test_load_chapter_map_when_toc_is_empty_rejects_chapter_grouping(
    tmp_path: Path,
) -> None:
    toc = tmp_path / "toc.md"
    _ = toc.write_text("# Table of Contents\n\n## Contents\n", encoding="utf-8")

    with pytest.raises(ChapterMapUnavailableError, match="no chapters"):
        _ = load_chapter_map(toc)


def test_load_chapter_map_applies_printed_page_offset_to_source_pages(
    tmp_path: Path,
) -> None:
    toc = tmp_path / "toc.md"
    _ = toc.write_text(
        chr(10).join(
            [
                "# Table of Contents",
                "",
                "## Contents",
                "",
                "- page: 12",
                "  title: 제1장 기초",
                "- page: 38",
                "  title: 제2장 응용",
            ]
        ),
        encoding="utf-8",
    )

    chapter_map = load_chapter_map(toc, offset=-2)

    assert chapter_map.chapter_for(PageNumber(10)) == "제1장 기초"
    assert chapter_map.chapter_for(PageNumber(36)) == "제2장 응용"


def test_load_chapter_map_when_chapters_share_a_page_keeps_both_boundaries(
    tmp_path: Path,
) -> None:
    # Given: two adjacent contents entries begin on the same printed page.
    toc = tmp_path / "toc.md"
    _ = toc.write_text(
        chr(10).join(
            (
                "# Table of Contents",
                "",
                "## Contents",
                "",
                "- page: 51",
                "  title: 3.1 물리적 성질",
                "- page: 51",
                "  title: 3.2 정수력학",
            )
        ),
        encoding="utf-8",
    )

    # When: the chapter map is loaded.
    chapter_map = load_chapter_map(toc)

    # Then: both same-page boundaries remain available in source order.
    assert tuple(boundary.page for boundary in chapter_map.boundaries) == (
        PageNumber(51),
        PageNumber(51),
    )


def test_load_chapter_map_when_toc_is_missing_rejects_chapter_grouping(
    tmp_path: Path,
) -> None:
    toc = tmp_path / "toc.md"

    with pytest.raises(ChapterMapUnavailableError, match=r"toc\.md is required"):
        _ = load_chapter_map(toc)


def test_load_chapter_map_when_multiple_parts_exist_assigns_each_chapter(
    tmp_path: Path,
) -> None:
    # Given: two independent part sections with one chapter each.
    path = tmp_path / "toc.md"
    content = (
        "## Part A | page: 1\n"
        "### Chapter A | page: 2\n"
        "## Part B | page: 10\n"
        "### Chapter B | page: 11"
    )

    # When: each section is parsed independently and merged in source order.
    _ = path.write_text(content, encoding="utf-8")
    chapter_map = load_chapter_map(path)

    # Then: chapter ownership does not leak across section boundaries.
    assert tuple(boundary.part for boundary in chapter_map.boundaries) == (
        "Part A",
        "Part B",
    )


def test_load_chapter_map_when_entry_has_no_title_rejects_it(tmp_path: Path) -> None:
    # Given: a contents list with an incomplete chapter entry.
    toc = tmp_path / "toc.md"
    _ = toc.write_text("## Contents\n- page: 2\n", encoding="utf-8")

    # When / Then: the parser reports the invalid boundary instead of dropping it.
    with pytest.raises(ChapterMapUnavailableError, match="positive page and title"):
        _ = load_chapter_map(toc)
