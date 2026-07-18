from pathlib import Path

from typer.testing import CliRunner

from cli import app


def test_cli_when_input_file_is_missing_exits_with_usage_error(
    tmp_path: Path,
) -> None:
    # Given: a PDF path that does not exist.
    missing_pdf = tmp_path / "missing.pdf"
    runner = CliRunner()

    # When: the OCR CLI receives the path.
    result = runner.invoke(app, [str(missing_pdf)])

    # Then: it reports a usage error that identifies the missing path.
    assert result.exit_code == 2
    assert str(missing_pdf) in result.output
