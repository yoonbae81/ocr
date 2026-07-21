from pathlib import Path

from PIL import Image

from adapters.output.markdown import MarkdownPageExporter
from domain import PageMarkdown, PageNumber, SourcePage


def test_export_writes_numbered_markdown_without_page_image(tmp_path: Path) -> None:
    source_image = tmp_path / "source.jpg"
    Image.new("RGB", (20, 10), "white").save(source_image)
    page = SourcePage(PageNumber(2), source_image)

    MarkdownPageExporter().export(
        PageMarkdown(page, "text"), tmp_path / "book", False
    )

    assert (tmp_path / "book" / "2.md").read_text() == "text\n"
    assert not (tmp_path / "book" / "img").exists()


def test_export_normalizes_table_breaks_and_images_to_markdown(tmp_path: Path) -> None:
    source_image = tmp_path / "source.jpg"
    Image.new("RGB", (20, 10), "white").save(source_image)
    page = SourcePage(PageNumber(2), source_image)

    MarkdownPageExporter().export(
        PageMarkdown(
            page,
            '<div style="text-align: center;">Figure caption</div>\n\n'
            '<table><tr><td>first\\nsecond</td></tr></table>\n\n'
            '<div style="text-align: center;"><img '
            'src="imgs/img_in_image_box_1_2_9_8.jpg" '
            'alt="Figure" width="50%" /></div>',
        ),
        tmp_path / "book",
        False,
    )

    assert (tmp_path / "book" / "2.md").read_text() == (
        "Figure caption\n\n"
        "<table><tr><td>first<br/>second</td></tr></table>\n\n"
        "![Figure](img/2_1_2_9_8.jpg)\n"
    )
    with Image.open(tmp_path / "book" / "img" / "2_1_2_9_8.jpg") as image:
        assert image.size == (8, 6)


def test_export_strips_latex_underline_markup(tmp_path: Path) -> None:
    source_image = tmp_path / "source.jpg"
    Image.new("RGB", (20, 10), "white").save(source_image)
    page = SourcePage(PageNumber(2), source_image)

    MarkdownPageExporter().export(
        PageMarkdown(
            page,
            "Before $ \\underline{\\text{underlined content}} $ after.",
        ),
        tmp_path / "book",
        False,
    )

    assert (tmp_path / "book" / "2.md").read_text() == "Before underlined content after.\n"
