from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cli
from command_runtime import RunOptions
from domain import PageNumber


runner = CliRunner()
INVALID_USAGE_EXIT_CODE = 2


@pytest.mark.parametrize("pages", ["0", "-1", "abc", "1-", "3-1"])
def test_run_rejects_invalid_pages(
    pages: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "book.pdf"
    source.touch()
    calls: list[Path] = []

    def fake_run_source(source: Path, *_: object) -> int:
        calls.append(source)
        return 1

    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, [str(source), pages])

    assert result.exit_code == INVALID_USAGE_EXIT_CODE
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
    calls: list[tuple[str, tuple[PageNumber, ...] | None]] = []
    recognizers: list[object] = []

    class FakeRecognizer:
        pass

    class FakeBackend:
        cache_namespace = "fake"

        def __init__(self) -> None:
            self.recognizer = FakeRecognizer()

        def get_recognizer(self) -> FakeRecognizer:
            return self.recognizer

    backend = FakeBackend()

    @contextmanager
    def fake_open_backend(*_: object) -> Iterator[FakeBackend]:
        yield backend

    def fake_run_source(
        source: Path,
        options: RunOptions,
        recognition_backend: FakeBackend,
    ) -> int:
        calls.append((source.name, options.pages))
        recognizers.append(recognition_backend.get_recognizer())
        return 1

    monkeypatch.setattr(cli, "open_backend", fake_open_backend)
    monkeypatch.setattr(cli, "run_source", fake_run_source)

    result = runner.invoke(cli.app, ["*.pdf", "2-3"])

    assert result.exit_code == 0
    assert calls == [
        ("a.pdf", (PageNumber(2), PageNumber(3))),
        ("b.pdf", (PageNumber(2), PageNumber(3))),
    ]
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


def test_openvino_backend_requires_model_path(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    source.touch()

    result = runner.invoke(cli.app, [str(source), "1", "--backend", "openvino"])

    assert result.exit_code == INVALID_USAGE_EXIT_CODE
    assert "--vlm-model-path is required" in result.output


def test_openvino_backend_rejects_mlx_server_options(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    source.touch()

    result = runner.invoke(
        cli.app,
        [
            str(source),
            "1",
            "--backend",
            "openvino",
            "--vlm-model-path",
            str(tmp_path / "model"),
            "--server-url",
            "http://127.0.0.1:9010",
        ],
    )

    assert result.exit_code == INVALID_USAGE_EXIT_CODE
    assert "only valid for MLX" in result.output
