from pathlib import Path

import pytest
from typer.testing import CliRunner

from application.checkpoint import GroupName, checkpoint_batches
from application.ports.recognizer import RecognizerPort
from cli import app, default_group
from domain.chapters import ChapterBoundary, ChapterMap
from domain.content import ImagePage, PageNumber, SourceKind
from settings import ModelName, Settings


class SuccessfulRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = (page, prompt)
        return "recognized"


def test_default_group_when_toc_exists_selects_chapter(tmp_path: Path) -> None:
    # Given: a workspace contains a table of contents.
    _ = (tmp_path / "toc.md").write_text("# Table of Contents\n", encoding="utf-8")

    # When: the default grouping policy is resolved.
    selected = default_group(tmp_path)

    # Then: chapter grouping is selected.
    assert selected is GroupName.CHAPTER


def test_default_group_when_toc_is_missing_selects_page(tmp_path: Path) -> None:
    # Given: a workspace has no table of contents.

    # When: the default grouping policy is resolved.
    selected = default_group(tmp_path)

    # Then: page grouping is selected.
    assert selected is GroupName.PAGE


def test_checkpoint_batches_when_chapters_change_split_at_boundaries() -> None:
    # Given: three source pages span two TOC chapters.
    pages = tuple(
        ImagePage(
            page=PageNumber(number),
            image=b"png",
            media_type="image/png",
            source=SourceKind.IMAGE,
        )
        for number in (1, 2, 3)
    )
    chapter_map = ChapterMap(
        boundaries=(
            ChapterBoundary(page=PageNumber(1), title="one"),
            ChapterBoundary(page=PageNumber(3), title="two"),
        )
    )

    # When: checkpoint batches are computed for chapter grouping.
    batches = checkpoint_batches(pages, GroupName.CHAPTER, chapter_map)

    # Then: each completed chapter is an independent persistence batch.
    assert [[page.page for page in batch] for batch in batches] == [[1, 2], [3]]


def test_cli_when_model_is_omitted_uses_configured_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: settings select Gemini and no model option is supplied.
    image_path = tmp_path / "scan.png"
    _ = image_path.write_bytes(b"png")
    settings = Settings(
        paddle_endpoint="http://paddle.test:8111/",
        paddle_model="paddle-model",
        codex_model="codex-model",
        agy_model="agy-model",
        default_model=ModelName.GEMINI,
    )
    selected_models: list[str] = []

    def factory(model: str, *, settings: Settings, effort: str) -> RecognizerPort:
        _ = (settings, effort)
        selected_models.append(model)
        return SuccessfulRecognizer()

    monkeypatch.setattr("cli._settings", lambda: settings)
    monkeypatch.setattr("cli.recognizer_for", factory)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # When: OCR runs without an explicit model option.
    _ = runner.invoke(app, ["scan.png", "1", "--group", "page"])

    # Then: recognition receives the environment-configured model selection.
    assert selected_models == ["gemini"]
