from base64 import b64decode
from pathlib import Path
from typing import Protocol
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
import pytest
from typer.testing import CliRunner

from adapters.recognition.errors import RecognitionError
from application.ports.recognizer import RecognizerPort
from cli import app
from domain.content import ImagePage
from settings import Settings


class RecordingRecognizer:
    """Recognizer fake that records the prompt passed by the CLI."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.pages: list[int] = []

    def recognize(self, page: ImagePage, prompt: str) -> str:
        """Record the configured prompt and return deterministic Markdown."""
        self.prompts.append(prompt)
        self.pages.append(page.page)
        return f"recognized {page.page}"


class RecognizerFactory(Protocol):
    def __call__(
        self,
        model: str,
        *,
        settings: Settings,
        effort: str,
    ) -> RecognizerPort: ...


class FailingFirstRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        if page.page == 1:
            raise RecognitionError(detail="model unavailable")
        return f"recognized {page.page}"


class FailingChapterRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = (page, prompt)
        raise RecognitionError(detail="recognition API request failed")


class FailingSecondPageRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        if page.page == 2:
            raise RecognitionError(detail="page two unavailable")
        return f"recognized {page.page}"


class FailsFirstAttemptRecognizer:
    def __init__(self) -> None:
        self.pages: list[int] = []
        self._failed: bool = False

    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        self.pages.append(page.page)
        if page.page == 1 and not self._failed:
            self._failed = True
            raise RecognitionError(detail="model unavailable")
        return f"recognized {page.page}"


class BookmarklessChapterRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        if page.page == 1:
            return "제1장 첫 장 .... 1"
        return "첫 장의 계속"


class ZipChapterRecognizer:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        self.pages.append(page.page)
        if page.page == 5:
            return "1장 에너지 자원과 전력 ... 11\nChapter 2 Steam turbines ... 14"
        return f"logical page {page.page}"


def _png_bytes() -> bytes:
    return b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII="
    )


def _recognizer_factory(
    recognizer: RecognizerPort,
) -> RecognizerFactory:
    def factory(model: str, *, settings: Settings, effort: str) -> RecognizerPort:
        _ = (model, settings, effort)
        return recognizer

    return factory


def _blank_pdf(
    path: Path,
    page_count: int,
) -> None:
    with fitz.open() as pdf:
        for _ in range(page_count):
            _ = pdf.new_page()
        pdf.save(path)


def _write_toc(path: Path, entries: tuple[tuple[int, str], ...]) -> None:
    content = "# Table of Contents\n\n## Chapters\n\n"
    content += "".join(f"- page: {page}\n  title: {title}\n" for page, title in entries)
    _ = (path / "toc.md").write_text(content, encoding="utf-8")


@pytest.mark.parametrize("model", ["gpt", "gemini"])
def test_cli_when_workspace_prompt_is_absent_uses_a_default_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    # Given: an image workspace with no local prompt file.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: page output is requested.
    result = runner.invoke(
        app,
        ["scan.png", "1", "--model", model, "--group", "page"],
    )

    # Then: recognition receives a built-in prompt and no workspace file is created.
    assert result.exit_code == 0
    assert not (tmp_path / "prompt.md").exists()
    assert (tmp_path / "output" / "1.md").is_file()
    assert len(recognizer.prompts) == 1
    assert recognizer.prompts[0]


def test_cli_when_workspace_prompt_exists_uses_it_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an image workspace with a structurally distinct local prompt marker.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    prompt_path = tmp_path / "prompt.md"
    workspace_prompt = "<!-- prompt-id: workspace -->\n"
    _ = prompt_path.write_text(workspace_prompt, encoding="utf-8")
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: page output is requested.
    result = runner.invoke(
        app,
        ["scan.png", "1", "--model", "gpt", "--group", "page"],
    )

    # Then: the structural marker is supplied to recognition and remains unchanged.
    assert result.exit_code == 0
    assert recognizer.prompts == [workspace_prompt]
    assert prompt_path.read_text(encoding="utf-8") == workspace_prompt


def test_cli_when_parent_workspace_prompt_exists_uses_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a book workspace inherits a common prompt from its workspace directory.
    workspace_path = tmp_path / "workspace"
    book_path = workspace_path / "book"
    book_path.mkdir(parents=True)
    image_path = book_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    workspace_prompt = "<!-- prompt-id: common-workspace -->\n"
    _ = (workspace_path / "prompt.md").write_text(workspace_prompt, encoding="utf-8")
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(book_path)

    # When: page output is requested from the book directory.
    result = CliRunner().invoke(
        app,
        ["scan.png", "1", "--model", "gpt", "--group", "page"],
    )

    # Then: recognition receives the inherited workspace prompt.
    assert result.exit_code == 0
    assert recognizer.prompts == [workspace_prompt]


def test_cli_when_paddle_is_selected_with_prompt_ignores_it_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a Paddle workspace includes a prompt for the backend.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    _ = (tmp_path / "prompt.md").write_text(
        "<!-- prompt-id: paddle-workspace -->\n",
        encoding="utf-8",
    )
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)

    # When: OCR is requested through the Paddle selector.
    result = CliRunner().invoke(
        app,
        ["scan.png", "1", "--model", "paddle", "--group", "page"],
    )

    # Then: recognition does not receive an unsupported prompt and produces an artifact.
    assert result.exit_code == 0
    assert recognizer.prompts == [""]
    assert (tmp_path / "output" / "1.md").is_file()


def test_cli_when_page_range_is_descending_leaves_workspace_unmodified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an image workspace and an invalid descending range.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: the invalid range is passed to the CLI.
    result = runner.invoke(app, ["scan.png", "2-1"])

    # Then: validation fails before prompt or output artifacts are created.
    assert result.exit_code == 2
    assert not (tmp_path / "prompt.md").exists()
    assert not (tmp_path / "output").exists()


def test_cli_when_effort_is_unsupported_rejects_before_creating_workspace_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an image workspace with no prompt or output directory.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: a model that has no effort capability receives a non-default effort.
    result = runner.invoke(
        app,
        ["scan.png", "1", "--model", "paddle", "--effort", "high", "--group", "page"],
    )

    # Then: it returns a usage error without writing workspace artifacts.
    assert result.exit_code == 2
    assert "does not support effort" in result.output
    assert not (tmp_path / "prompt.md").exists()
    assert not (tmp_path / "output").exists()


def test_cli_when_a_page_recognition_fails_continues_and_records_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a two-page scanned PDF and a recognizer that fails only its first page.
    pdf_path = tmp_path / "scans.pdf"
    with fitz.open() as pdf:
        _ = pdf.new_page()
        _ = pdf.new_page()
        pdf.save(pdf_path)
    monkeypatch.setattr(
        "cli.recognizer_for", _recognizer_factory(FailingFirstRecognizer())
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: both pages are requested as independent artifacts.
    result = runner.invoke(app, ["scans.pdf", "1-2", "--group", "page"])

    # Then: later pages are retained while the failed page is recorded in status.
    assert result.exit_code == 1
    assert not (tmp_path / "output" / "1.md").exists()
    assert (tmp_path / "output" / "2.md").is_file()
    assert "- 1: model unavailable" in (tmp_path / "output" / "status.md").read_text(
        encoding="utf-8"
    )


def test_cli_when_chapter_recognition_fails_preserves_primary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 1)
    _write_toc(tmp_path, ((1, "Part one"),))
    monkeypatch.setattr(
        "cli.recognizer_for", _recognizer_factory(FailingChapterRecognizer())
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: the real Typer command traverses the unhandled chapter-recognition path.
    result = runner.invoke(app, ["scans.pdf", "1", "--group", "chapter"])

    # Then: the primary recognition error survives Click's traceback handling intact.
    assert result.exit_code != 0
    assert result.exception is not None
    status = (tmp_path / "output" / "status.md").read_text(encoding="utf-8")
    assert "recognition API request failed" in status
    assert "super(type, obj)" not in str(result.exception)


def test_cli_when_later_chapter_fails_persists_completed_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: two chapters where only the second chapter fails recognition.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    _write_toc(tmp_path, ((1, "Part one"), (2, "Part two")))
    monkeypatch.setattr(
        "cli.recognizer_for", _recognizer_factory(FailingSecondPageRecognizer())
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: both chapters are processed in one invocation.
    result = runner.invoke(app, ["scans.pdf", "1-2", "--group", "chapter"])

    # Then: the completed first chapter survives the later page failure.
    assert result.exit_code == 1
    assert (tmp_path / "output" / "Part one.md").is_file()
    status = (tmp_path / "output" / "status.md").read_text(encoding="utf-8")
    assert "- 1\n" in status
    assert "- 2: page two unavailable" in status


def test_cli_when_a_failed_page_is_retried_merges_status_and_skips_completed_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a two-page scan whose first recognition attempt fails only page one.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    recognizer = FailsFirstAttemptRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: the same selected range is invoked again after the failed page recovers.
    first = runner.invoke(app, ["scans.pdf", "1-2", "--group", "page"])
    second = runner.invoke(
        app, ["scans.pdf", "1-2", "--group", "page", "--retry-failed"]
    )

    # Then: page two is not recognized twice, page one is retried, and status is merged.
    assert first.exit_code == 1
    assert second.exit_code == 0
    assert recognizer.pages == [1, 2, 1]
    status = (tmp_path / "output" / "status.md").read_text(encoding="utf-8")
    assert "- 1\n" in status
    assert "- 2\n" in status
    assert "- none" in status.split("## Failed\n", maxsplit=1)[1]


def test_cli_when_book_ranges_are_non_overlapping_appends_without_reprocessing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a two-page scanned PDF and one recognizer shared by two invocations.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: each page is requested separately as part of the book artifact.
    first = runner.invoke(app, ["scans.pdf", "1", "--group", "book"])
    second = runner.invoke(app, ["scans.pdf", "2", "--group", "book"])

    # Then: both rendered pages remain in one artifact and each was recognized once.
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert recognizer.pages == [1, 2]
    book = (tmp_path / "output" / "book.md").read_text(encoding="utf-8")
    assert "recognized 1" in book
    assert "recognized 2" in book


def test_cli_when_book_page_retry_succeeds_orders_rendered_pages_by_page_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: page one fails once while page two completes in the first book run.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    recognizer = FailsFirstAttemptRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: the failed page is retried after page two was already written.
    first = runner.invoke(app, ["scans.pdf", "1-2", "--group", "book"])
    second = runner.invoke(app, ["scans.pdf", "1", "--group", "book", "--retry-failed"])

    # Then: the persisted book has one ascending block per completed page.
    assert first.exit_code == 1
    assert second.exit_code == 0
    book = (tmp_path / "output" / "book.md").read_text(encoding="utf-8")
    assert book.index("<!-- page: 1 -->") < book.index("<!-- page: 2 -->")
    assert book.count("<!-- page: 1 -->") == 1
    assert book.count("<!-- page: 2 -->") == 1


def test_cli_when_chapter_page_retry_succeeds_orders_rendered_pages_by_page_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one chapter where page one fails before page two completes.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    _write_toc(tmp_path, ((1, "Part one"),))
    recognizer = FailsFirstAttemptRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: the failed page is retried in a following chapter invocation.
    first = runner.invoke(app, ["scans.pdf", "1-2", "--group", "chapter"])
    second = runner.invoke(
        app, ["scans.pdf", "1", "--group", "chapter", "--retry-failed"]
    )

    # Then: the chapter artifact remains page ordered without duplicate blocks.
    assert first.exit_code == 1
    assert second.exit_code == 0
    chapter = (tmp_path / "output" / "Part one.md").read_text(encoding="utf-8")
    assert chapter.index("<!-- page: 1 -->") < chapter.index("<!-- page: 2 -->")
    assert chapter.count("<!-- page: 1 -->") == 1
    assert chapter.count("<!-- page: 2 -->") == 1


def test_cli_when_chapter_ranges_are_non_overlapping_appends_under_one_stable_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: two scanned pages belonging to the same PDF chapter.
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    _write_toc(tmp_path, ((1, "Part one"),))
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: chapter output is produced from separate page-range invocations.
    first = runner.invoke(app, ["scans.pdf", "1", "--group", "chapter"])
    second = runner.invoke(app, ["scans.pdf", "2", "--group", "chapter"])

    # Then: one stable chapter artifact retains both newly rendered page sections.
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert recognizer.pages == [1, 2]
    chapter = (tmp_path / "output" / "Part one.md").read_text(encoding="utf-8")
    assert "recognized 1" in chapter
    assert "recognized 2" in chapter


def test_cli_when_chapter_grouping_without_toc_stops_before_ocr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["scans.pdf", "1", "--group", "chapter"])

    assert result.exit_code == 2
    assert "toc.md is required" in result.output
    assert recognizer.pages == []
    assert not (tmp_path / "prompt.md").exists()
    assert not (tmp_path / "output").exists()


def test_cli_when_toc_offset_is_given_maps_printed_pages_to_input_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "scans.pdf"
    _blank_pdf(pdf_path, 2)
    _write_toc(tmp_path, ((1, "Part one"),))
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["scans.pdf", "1-2", "--group", "chapter", "--toc-offset", "1"],
    )

    assert result.exit_code == 0
    assert (tmp_path / "output" / "frontmatter.md").is_file()
    assert (tmp_path / "output" / "Part one.md").is_file()
    assert "<!-- page: 1 -->" in (tmp_path / "output" / "frontmatter.md").read_text(
        encoding="utf-8"
    )
    assert "<!-- page: 2 -->" in (tmp_path / "output" / "Part one.md").read_text(
        encoding="utf-8"
    )


def test_cli_when_zip_chapter_grouping_uses_printed_toc_page_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a ZIP scan with a contents entry on page five for logical page eleven.
    archive_path = tmp_path / "발전공학.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for page in range(1, 16):
            archive.writestr(f"발전공학/510{page:03}.jpg", _png_bytes())
    toc_sections = (
        "# Table of Contents",
        "## 발전설비 | page: 1",
        "### 1장 에너지 자원과 전력 | page: 1",
        "### Chapter 2 Steam turbines | page: 14",
    )
    toc_content = "\n\n".join(toc_sections) + "\n"
    _ = (tmp_path / "toc.md").write_text(
        toc_content,
        encoding="utf-8",
    )
    recognizer = ZipChapterRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: a chapter range is transcribed directly from the archive.
    result = runner.invoke(app, ["발전공학.zip", "1-15", "--group", "chapter"])

    assert result.exit_code == 0
    assert sorted(recognizer.pages) == list(range(1, 16))
    parent = tmp_path / "output" / "발전설비"
    first_chapter = (parent / "1장 에너지 자원과 전력.md").read_text(encoding="utf-8")
    second_chapter = (parent / "Chapter 2 Steam turbines.md").read_text(
        encoding="utf-8"
    )
    assert "<!-- page: 1 -->" in first_chapter
    assert "<!-- page: 13 -->" in first_chapter
    assert "<!-- page: 14 -->" in second_chapter
    assert "<!-- page: 15 -->" in second_chapter


def test_cli_when_all_selected_pages_are_already_completed_keeps_artifacts_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a completed single-page book output.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(_png_bytes())
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["scan.png", "1", "--group", "page"])
    artifact = tmp_path / "output" / "1.md"
    before = artifact.read_text(encoding="utf-8")

    # When: the already completed page is requested again.
    second = runner.invoke(app, ["scan.png", "1", "--group", "page"])

    # Then: no recognition or output rewrite occurs.
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert recognizer.pages == [1]
    assert artifact.read_text(encoding="utf-8") == before
