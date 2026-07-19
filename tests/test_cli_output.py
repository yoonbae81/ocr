from base64 import b64decode
from pathlib import Path
from typing import Protocol, override
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
import pytest
from typer.testing import CliRunner

from adapters.recognition.errors import RecognitionError
from application.ports.recognizer import RecognizerPort
from cli import app
from domain.content import ImagePage
from settings import Settings


class RecognizerFactory(Protocol):
    def __call__(
        self,
        *,
        settings: Settings,
    ) -> RecognizerPort: ...


class RecordingRecognizer:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        self.pages.append(page.page)
        return f"recognized {page.page}"


class FailsFirstAttemptRecognizer(RecordingRecognizer):
    def __init__(self) -> None:
        super().__init__()
        self._failed: bool = False

    @override
    def recognize(self, page: ImagePage, prompt: str) -> str:
        body = super().recognize(page, prompt)
        if page.page == 1 and not self._failed:
            self._failed = True
            raise RecognitionError(detail="model unavailable")
        return body


def _png_bytes() -> bytes:
    encoded = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/"
        "fteaysAAAAASUVORK5CYII="
    )
    return b64decode(encoded)


def _recognizer_factory(recognizer: RecognizerPort) -> RecognizerFactory:
    def factory(*, settings: Settings) -> RecognizerPort:
        _ = settings
        return recognizer

    return factory


def _blank_pdf(path: Path, page_count: int) -> None:
    with fitz.open() as pdf:
        for _ in range(page_count):
            _ = pdf.new_page()
        pdf.save(path)


def test_cli_when_pdf_pages_are_requested_writes_one_canonical_file_per_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a two-page local PDF and deterministic recognition.
    _blank_pdf(tmp_path / "book.pdf", 2)
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)

    # When: both physical pages are requested.
    result = CliRunner().invoke(app, ["book.pdf", "1-2"])

    # Then: each page contains its own physical-page metadata and body.
    assert result.exit_code == 0
    assert (
        (tmp_path / "book" / "0001.md")
        .read_text(encoding="utf-8")
        .endswith("page: 1\n---\n\nrecognized 1\n")
    )
    assert (
        (tmp_path / "book" / "0002.md")
        .read_text(encoding="utf-8")
        .endswith("page: 2\n---\n\nrecognized 2\n")
    )


@pytest.mark.parametrize("input_name", ["scan.png", "scans.zip"])
def test_cli_when_image_or_zip_is_requested_uses_the_same_page_output_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    input_name: str,
) -> None:
    # Given: one image source in either supported image container.
    if input_name.endswith(".zip"):
        with ZipFile(tmp_path / input_name, "w", ZIP_DEFLATED) as archive:
            archive.writestr("page-001.png", _png_bytes())
    else:
        _ = (tmp_path / input_name).write_bytes(_png_bytes())
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)

    # When: logical page one is transcribed.
    result = CliRunner().invoke(app, [input_name, "1"])

    # Then: its canonical file records the original input filename.
    assert result.exit_code == 0
    result_directory = tmp_path / Path(input_name).stem
    assert f'source: "{input_name}"' in (result_directory / "0001.md").read_text(
        encoding="utf-8"
    )


def test_cli_when_completed_pages_are_requested_again_does_not_recognize_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: one completed local image page.
    _ = (tmp_path / "scan.png").write_bytes(_png_bytes())
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["scan.png", "1"])

    # When: the same source page is selected again.
    second = runner.invoke(app, ["scan.png", "1"])

    # Then: the stored completion state prevents a second OCR call.
    assert first.exit_code == second.exit_code == 0
    assert recognizer.pages == [1]


def test_cli_when_retrying_failed_pages_only_retries_the_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a PDF whose first page fails once while the second succeeds.
    _blank_pdf(tmp_path / "scans.pdf", 2)
    recognizer = FailsFirstAttemptRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["scans.pdf", "1-2"])

    # When: retry mode is invoked for the range.
    second = runner.invoke(app, ["scans.pdf", "1-2", "--retry-failed"])

    # Then: only the failed page is recognized again and state becomes complete.
    assert first.exit_code == 1
    assert second.exit_code == 0
    assert recognizer.pages == [1, 2, 1]
    assert (
        "- none"
        in (tmp_path / "scans" / "status.md")
        .read_text(encoding="utf-8")
        .split("## Failed\n", maxsplit=1)[1]
    )


def test_cli_when_a_different_input_uses_workspace_does_not_reuse_previous_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: two separately named image inputs sharing one work directory.
    _ = (tmp_path / "first.png").write_bytes(_png_bytes())
    _ = (tmp_path / "second.png").write_bytes(_png_bytes())
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["first.png", "1"])

    # When: the second input requests the same physical page number.
    second = runner.invoke(app, ["second.png", "1"])

    # Then: it is recognized rather than resumed from the first input state.
    assert first.exit_code == second.exit_code == 0
    assert recognizer.pages == [1, 1]
    assert 'source: "second.png"' in (tmp_path / "second" / "0001.md").read_text(
        encoding="utf-8"
    )


def test_cli_when_a_toc_file_is_present_produces_identical_page_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an image workspace with an unrelated contents file.
    _ = (tmp_path / "scan.png").write_bytes(_png_bytes())
    _ = (tmp_path / "toc.md").write_text("unrelated notes", encoding="utf-8")
    recognizer = RecordingRecognizer()
    monkeypatch.setattr("cli.recognizer_for", _recognizer_factory(recognizer))
    monkeypatch.chdir(tmp_path)

    # When: OCR runs normally.
    result = CliRunner().invoke(app, ["scan.png", "1"])

    # Then: the contents file has no effect on the canonical page artifact.
    assert result.exit_code == 0
    assert (tmp_path / "scan" / "0001.md").is_file()


def test_cli_help_does_not_offer_legacy_output_options() -> None:
    # Given: the executable command interface.
    runner = CliRunner()

    # When: help is requested.
    result = runner.invoke(app, ["ocr", "--help"])

    # Then: retired output controls are not part of the public CLI contract.
    assert result.exit_code == 0
    assert all(
        option not in result.output for option in ("--" + "group", "--" + "toc-offset")
    )
