from pathlib import Path

import pytest

from adapters.output.markdown import MarkdownOutput
from domain.content import (
    DocumentBundle,
    DocumentGroup,
    PageContent,
    PageNumber,
    SourceKind,
)
from domain.status import PageFailure, ProcessingStatus


def test_markdown_output_when_page_groups_are_written_uses_unpadded_page_names(
    tmp_path: Path,
) -> None:
    # Given: a format-neutral page bundle with provenance.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="1",
                pages=(
                    PageContent(
                        page=PageNumber(1),
                        body="recognized body",
                        source=SourceKind.PDF_RENDER,
                    ),
                ),
            ),
        )
    )
    output = MarkdownOutput(tmp_path / "output")

    # When: Markdown output persists the bundle.
    result = output.write(
        bundle,
        ProcessingStatus(
            completed=(PageNumber(1),),
            failures=(PageFailure(page=PageNumber(2), reason="model unavailable"),),
            current_chapter="제1장",
        ),
    )

    # Then: the page artifact and processing status preserve observable content.
    page_path = tmp_path / "output" / "1.md"
    status_path = tmp_path / "output" / "status.md"
    assert page_path in result.files
    assert page_path.read_text(encoding="utf-8").endswith("recognized body\n")
    page_contents = page_path.read_text(encoding="utf-8")
    assert page_contents.startswith("<!-- page: 1 -->\n\n")
    assert "<!-- source:" not in page_contents
    assert status_path in result.files
    assert "- 1" in status_path.read_text(encoding="utf-8")
    assert "- 2: model unavailable" in status_path.read_text(encoding="utf-8")
    assert "## Current Chapter\n제1장" in status_path.read_text(encoding="utf-8")
    assert output.load_status().current_chapter == "제1장"


def test_markdown_output_when_display_math_has_padding_writes_standard_mathjax_block(
    tmp_path: Path,
) -> None:
    # Given: OCR emits a display formula with surrounding whitespace.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="1",
                pages=(
                    PageContent(
                        page=PageNumber(1),
                        body=" $$ P_{0}=9.8QH[\\mathrm{kW}] $$ ",
                    ),
                ),
            ),
        )
    )

    # When: Markdown output persists the recognized page.
    _ = MarkdownOutput(tmp_path / "output").write(bundle, ProcessingStatus())

    # Then: the formula delimiters occupy their own lines for MathJax rendering.
    assert (tmp_path / "output" / "1.md").read_text(encoding="utf-8") == (
        "<!-- page: 1 -->\n\n$$\nP_{0}=9.8QH[\\mathrm{kW}]\n$$\n"
    )


def test_markdown_output_when_regex_rule_files_are_supplied_applies_them_in_order(
    tmp_path: Path,
) -> None:
    # Given: two declarative rules named in their intended processing order.
    rules = tmp_path / "rules"
    rules.mkdir()
    _ = (rules / "10-first.json").write_text(
        '{"before": "first", "after": "second"}', encoding="utf-8"
    )
    _ = (rules / "20-second.json").write_text(
        '{"before": "second", "after": "third"}', encoding="utf-8"
    )
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="1",
                pages=(PageContent(page=PageNumber(1), body="first"),),
            ),
        )
    )
    output = MarkdownOutput(
        tmp_path / "output",
        rule_directory=rules,
    )

    # When: the page is persisted through the rule-file processing pipeline.
    _ = output.write(bundle, ProcessingStatus())

    # Then: each rule receives the prior rule's output in filename order.
    assert (
        (tmp_path / "output" / "1.md").read_text(encoding="utf-8").endswith("third\n")
    )


def test_markdown_output_when_group_names_are_unsafe_uses_deterministic_safe_names(
    tmp_path: Path,
) -> None:
    # Given: a chapter-named group that cannot be used directly as a path.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="A/B: Intro",
                pages=(PageContent(page=PageNumber(1), body="body"),),
            ),
        )
    )

    # When: the chapter artifact is written.
    _ = MarkdownOutput(tmp_path / "output").write(bundle, ProcessingStatus())

    # Then: a deterministic, path-safe artifact name is used.
    assert (tmp_path / "output" / "AB Intro.md").is_file()


def test_markdown_output_when_chapter_has_parent_writes_under_parent_directory(
    tmp_path: Path,
) -> None:
    # Given: a chapter nested under a contents entry.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="Chapter 01 건축설비 기초지식",
                parent="PART 01 건축설비 계획",
                pages=(PageContent(page=PageNumber(14), body="body"),),
            ),
        )
    )

    # When: the chapter artifact is written.
    _ = MarkdownOutput(tmp_path / "output").write(bundle, ProcessingStatus())

    # Then: its contents hierarchy is preserved in the output path.
    assert (
        tmp_path
        / "output"
        / "PART 01 건축설비 계획"
        / "Chapter 01 건축설비 기초지식.md"
    ).is_file()


def test_markdown_output_when_chapter_is_written_in_two_runs_appends_to_stable_artifact(
    tmp_path: Path,
) -> None:
    # Given: two independently rendered pages belonging to one chapter.
    output = MarkdownOutput(tmp_path / "output")
    first = DocumentBundle(
        groups=(
            DocumentGroup(
                name="Part one",
                pages=(PageContent(page=PageNumber(1), body="first"),),
            ),
        )
    )
    second = DocumentBundle(
        groups=(
            DocumentGroup(
                name="Part one",
                pages=(PageContent(page=PageNumber(2), body="second"),),
            ),
        )
    )

    # When: each page is persisted in a separate output operation.
    _ = output.write(first, ProcessingStatus(completed=(PageNumber(1),)))
    _ = output.write(
        second,
        ProcessingStatus(completed=(PageNumber(1), PageNumber(2))),
    )

    # Then: the stable chapter file contains both rendered pages.
    chapter = tmp_path / "output" / "Part one.md"
    contents = chapter.read_text(encoding="utf-8")
    assert "first" in contents
    assert "second" in contents


def test_markdown_output_when_merging_legacy_source_markers_keeps_page_marker_only(
    tmp_path: Path,
) -> None:
    # Given: an existing chapter artifact written with the old source marker.
    output = MarkdownOutput(tmp_path / "output")
    chapter = tmp_path / "output" / "Part one.md"
    chapter.parent.mkdir()
    _ = chapter.write_text(
        "<!-- page: 1 -->\n<!-- source: pdf_text -->\n\nfirst\n",
        encoding="utf-8",
    )
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="Part one",
                pages=(PageContent(page=PageNumber(2), body="second"),),
            ),
        )
    )

    # When: a new page is merged into that artifact.
    _ = output.write(bundle, ProcessingStatus())

    # Then: the persisted artifact contains page boundaries without source metadata.
    contents = chapter.read_text(encoding="utf-8")
    assert "<!-- source:" not in contents
    assert sum(line.startswith("<!-- page: ") for line in contents.splitlines()) == 2


def test_markdown_output_when_body_contains_control_marker_escapes_it(
    tmp_path: Path,
) -> None:
    # Given: recognized content contains a line that resembles an internal page marker.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="Part one",
                pages=(
                    PageContent(
                        page=PageNumber(1),
                        body="before\n<!-- page: 2 -->\nafter",
                    ),
                ),
            ),
        )
    )

    # When: the content is written and later merged with another page.
    output = MarkdownOutput(tmp_path / "output")
    _ = output.write(bundle, ProcessingStatus())
    _ = output.write(
        DocumentBundle(
            groups=(
                DocumentGroup(
                    name="Part one",
                    pages=(PageContent(page=PageNumber(2), body="second"),),
                ),
            )
        ),
        ProcessingStatus(),
    )

    # Then: the content marker remains content and does not split or delete text.
    contents = (tmp_path / "output" / "Part one.md").read_text(encoding="utf-8")
    assert "before\n\\<!-- page: 2 -->\nafter" in contents
    assert sum(line.startswith("<!-- page: ") for line in contents.splitlines()) == 2


def test_markdown_output_when_groups_collide_rejects_ambiguous_artifacts(
    tmp_path: Path,
) -> None:
    # Given: two distinct groups normalize to the same output name.
    bundle = DocumentBundle(
        groups=(
            DocumentGroup(
                name="A/B",
                pages=(PageContent(page=PageNumber(1), body="a"),),
            ),
            DocumentGroup(
                name="AB",
                pages=(PageContent(page=PageNumber(2), body="b"),),
            ),
        )
    )

    # When / Then: output refuses to merge unrelated groups silently.
    with pytest.raises(ValueError, match="same output artifact"):
        _ = MarkdownOutput(tmp_path / "output").write(bundle, ProcessingStatus())


def test_load_status_when_sections_are_reordered_parses_them_independently(
    tmp_path: Path,
) -> None:
    # Given: a status file whose recognized sections are not writer ordered.
    output = tmp_path / "output"
    output.mkdir()
    _ = (output / "status.md").write_text(
        chr(10).join(
            (
                "# Status",
                "",
                "## Current Chapter",
                "Part one",
                "",
                "## Failed",
                "- 2: unavailable: retry later",
                "",
                "## Completed",
                "- 1",
                "- 3",
            )
        ),
        encoding="utf-8",
    )

    # When: persisted processing state is loaded.
    status = MarkdownOutput(output).load_status()

    # Then: each section is parsed without depending on traversal state.
    assert status == ProcessingStatus(
        completed=(PageNumber(1), PageNumber(3)),
        failures=(PageFailure(page=PageNumber(2), reason="unavailable: retry later"),),
        current_chapter="Part one",
    )
