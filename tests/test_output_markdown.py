from pathlib import Path

from adapters.output.markdown import MarkdownOutput
from domain.content import PageContent, PageNumber
from domain.status import PageFailure, ProcessingStatus


def test_markdown_output_when_pages_are_written_uses_padded_physical_page_files(
    tmp_path: Path,
) -> None:
    # Given: two OCR pages from one input file.
    pages = (
        PageContent(page=PageNumber(1), body="first body"),
        PageContent(page=PageNumber(10000), body="last body"),
    )
    output = MarkdownOutput(tmp_path / "output")

    # When: the canonical pages are persisted.
    result = output.write(
        pages,
        ProcessingStatus(completed=(PageNumber(1), PageNumber(10000))),
        source_name="book.pdf",
    )

    # Then: each source page owns exactly one independently named artifact.
    first = tmp_path / "output" / "0001.md"
    last = tmp_path / "output" / "10000.md"
    assert first in result.files
    assert first.read_text(encoding="utf-8") == (
        '---\nsource: "book.pdf"\npage: 1\n---\n\nfirst body\n'
    )
    assert last.read_text(encoding="utf-8").endswith("page: 10000\n---\n\nlast body\n")


def test_markdown_output_when_body_resembles_metadata_keeps_it_as_body(
    tmp_path: Path,
) -> None:
    # Given: OCR text containing legacy and front-matter-like control strings.
    body = "<!-- page: 9 -->\nsource: other.pdf\n---"
    output = MarkdownOutput(tmp_path / "output")

    # When: the page is written.
    _ = output.write(
        (PageContent(page=PageNumber(1), body=body),),
        ProcessingStatus(completed=(PageNumber(1),)),
        source_name='book "draft".pdf',
    )

    # Then: the fixed header is unambiguous and OCR text remains after its boundary.
    contents = (tmp_path / "output" / "0001.md").read_text(encoding="utf-8")
    assert contents.startswith('---\nsource: "book \\"draft\\".pdf"\npage: 1\n---\n\n')
    assert contents.endswith(f"{body}\n")


def test_markdown_output_when_status_is_loaded_uses_completed_failed_and_document(
    tmp_path: Path,
) -> None:
    # Given: persisted page-only processing state.
    output = MarkdownOutput(tmp_path / "output")
    _ = output.write(
        (),
        ProcessingStatus(
            document="/input/book.pdf",
            completed=(PageNumber(1),),
            failures=(
                PageFailure(page=PageNumber(2), reason="unavailable: retry later"),
            ),
        ),
        source_name="book.pdf",
    )

    # When: state is read for the same document.
    status = output.load_status(document="/input/book.pdf")

    # Then: retry decisions have all required page-level facts.
    assert status == ProcessingStatus(
        document="/input/book.pdf",
        completed=(PageNumber(1),),
        failures=(PageFailure(page=PageNumber(2), reason="unavailable: retry later"),),
    )
