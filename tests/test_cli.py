from __future__ import annotations

from pathlib import Path
from typing import Self

import pytest
from typer.testing import CliRunner

import cli
from command_runtime import RecognizerFactory, RunOptions
from domain import PageNumber


runner = CliRunner()


@pytest.mark.parametrize("pages", ["0", "-1", "abc", "1-", "3-1"])
def test_run_rejects_invalid_pages(
    pages: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid_usage_exit_code = 2
    source = tmp_path / "book.pdf"
    source.touch()
    calls: list[Path] = []

    def fake_run_source(source: Path, *_: object) -> int:
        calls.append(source)
        return 1

    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, [str(source), pages])

    assert result.exit_code == invalid_usage_exit_code
    assert calls == []


def test_run_processes_all_pages_when_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "book.pdf"
    source.touch()
    calls: list[tuple[Path, tuple[PageNumber, ...] | None]] = []

    def fake_run_source(
        source: Path,
        options: cli.RunOptions,
        *_: object,
    ) -> int:
        calls.append((source, options.pages))
        return 1

    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, [str(source)])

    assert result.exit_code == 0
    assert calls == [(source, None)]


def test_run_processes_quoted_wildcard_in_order_with_pages_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "b.pdf").touch()
    (tmp_path / "a.pdf").touch()
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, tuple[PageNumber, ...]]] = []
    recognizers: list[object] = []

    class FakeServer:
        starts = 0

        def __init__(self, model: str) -> None:
            del model
            self.url = "http://127.0.0.1:1234"

        def __enter__(self) -> Self:
            FakeServer.starts += 1
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class FakeRecognizer:
        def __init__(self, *_: object, **__: object) -> None:
            return None

    def fake_run_source(
        source: Path,
        options: RunOptions,
        recognizer: RecognizerFactory,
    ) -> int:
        calls.append((source.name, options.pages))
        recognizers.append(recognizer())
        return 1

    monkeypatch.setattr(cli, "MlxServerAdapter", FakeServer)
    monkeypatch.setattr(cli, "PaddleOcrVlAdapter", FakeRecognizer)
    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, ["*.pdf", "2-3"])

    assert result.exit_code == 0
    assert calls == [
        ("a.pdf", (PageNumber(2), PageNumber(3))),
        ("b.pdf", (PageNumber(2), PageNumber(3))),
    ]
    assert FakeServer.starts == 1
    assert recognizers[0] is recognizers[1]


def test_run_continues_after_one_source_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def fake_run_source(source: Path, *_: object) -> int:
        calls.append(source.name)
        if source.name == "a.pdf":
            raise RuntimeError("broken PDF")
        return 1

    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, ["*.pdf", "1"])

    assert result.exit_code == 1
    assert calls == ["a.pdf", "b.pdf"]
    assert "broken PDF" in result.output


def test_absolute_wildcard_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "book.pdf"
    source.touch()
    calls: list[Path] = []

    def fake_run_source(source: Path, *_: object) -> int:
        calls.append(source)
        return 1

    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, [str(tmp_path / "*.pdf"), "1"])

    assert result.exit_code == 0
    assert calls == [source.resolve()]
