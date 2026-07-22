from pathlib import Path

import pytest

from backend_config import BackendKind
from install_config import write_install_config
from settings import load_settings


EXPECTED_BATCH_SIZE = 32


def test_settings_precedence_is_environment_project_then_installed(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "installed.env"
    installed.write_text(
        'OCR_BACKEND="openvino"\n'
        'OCR_VLM_MODEL_PATH="installed-model"\n'
        'OCR_VLM_BATCH_SIZE="8"\n',
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text(
        'OCR_VLM_MODEL_PATH="project-model"\nOCR_VLM_BATCH_SIZE="16"\n',
        encoding="utf-8",
    )

    settings = load_settings(
        project,
        {
            "OCR_CONFIG_FILE": str(installed),
            "OCR_VLM_BATCH_SIZE": "32",
        },
    )

    assert settings.backend is BackendKind.OPENVINO
    assert settings.vlm_model_path == Path("project-model")
    assert settings.vlm_batch_size == EXPECTED_BATCH_SIZE


def test_install_config_writes_openvino_defaults_and_preserves_other_keys(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ocr.env"
    target.write_text("UNRELATED=value\nOCR_BACKEND=mlx\n", encoding="utf-8")
    model = tmp_path / "model with spaces"
    layout = tmp_path / "layout.xml"
    environment = {
        "OCR_CONFIG_FILE": str(target),
        "OCR_VLM_MODEL_PATH": str(model),
        "OCR_LAYOUT_MODEL_PATH": str(layout),
    }

    written = write_install_config(BackendKind.OPENVINO, environment)
    settings = load_settings(
        tmp_path / "empty", {"OCR_CONFIG_FILE": str(target)}
    )

    assert written == target
    assert "UNRELATED=value" in target.read_text(encoding="utf-8")
    assert settings.backend is BackendKind.OPENVINO
    assert settings.vlm_model_path == model
    assert settings.layout_model_path == layout


def test_openvino_install_requires_a_vlm_model_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="OCR_VLM_MODEL_PATH must be set"):
        write_install_config(
            BackendKind.OPENVINO,
            {"OCR_CONFIG_FILE": str(tmp_path / "ocr.env")},
        )
