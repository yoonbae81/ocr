from pathlib import Path
from typing import Literal

from PIL import Image
import pytest

from adapters.output import markdown as markdown_postprocessor
from adapters.output.markdown import (
    _apply_regex_rules,
    _load_regex_rules,
    normalize_markdown,
)

from domain import PageMarkdown, PageNumber, SourcePage


def test_normalize_markdown_removes_supported_ocr_residue(tmp_path: Path) -> None:
    source_image = tmp_path / "source.jpg"
    source_image.write_bytes(b"source")
    page = SourcePage(PageNumber(2), source_image)

    normalized = normalize_markdown(
        PageMarkdown(
            page,
            '<div style="text-align: center;">Caption</div>\n\n'
            "<table><tr><td>first\\nsecond</td></tr></table>\n\n"
            "Before $ \\underline{\\text{underlined content}} $ after.",
        ),
        tmp_path / "img",
    )

    assert normalized == (
        "Caption\n\n"
        "<table><tr><td>first<br/>second</td></tr></table>\n\n"
        "Before underlined content after."
    )


def test_regex_rules_load_from_tab_separated_text_file(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.txt"
    rules_path.write_text("(?i)source\treplacement\n", encoding="utf-8")

    rules = _load_regex_rules(rules_path)

    assert _apply_regex_rules("SOURCE text", rules) == "replacement text"


def test_normalize_markdown_opens_source_once_for_multiple_crops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_image = tmp_path / "source.jpg"
    Image.new("RGB", (20, 10), "white").save(source_image)
    page = SourcePage(PageNumber(2), source_image)
    opened = 0
    original_open = markdown_postprocessor.Image.open

    def count_open(
        path: str | Path,
        mode: Literal["r"] = "r",
        formats: list[str] | tuple[str, ...] | None = None,
    ) -> Image.Image:
        nonlocal opened
        opened += 1
        return original_open(path, mode, formats)

    monkeypatch.setattr(markdown_postprocessor.Image, "open", count_open)

    normalized = normalize_markdown(
        PageMarkdown(
            page,
            '<div><img src="img_in_image_box_1_2_9_8.jpg" alt="First" /></div>'
            '<div><img src="img_in_image_box_2_1_8_7.jpg" alt="Second" /></div>',
        ),
        tmp_path / "img",
    )

    assert opened == 1
    assert normalized == (
        "![First](img/2_1_2_9_8.jpg)![Second](img/2_2_1_8_7.jpg)"
    )
