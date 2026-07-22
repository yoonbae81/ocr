"""Create the persistent dotenv defaults used by the installed OCR command."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values

from backend_config import DEFAULT_MLX_MODEL, BackendKind
from settings import user_config_path


def write_install_config(backend: BackendKind, environ: dict[str, str]) -> Path:
    """Atomically write backend defaults while preserving unrelated settings."""
    target = user_config_path(environ)
    vlm_model_path = environ.get("OCR_VLM_MODEL_PATH", "").strip()
    if backend is BackendKind.OPENVINO and not vlm_model_path:
        raise ValueError(
            "OCR_VLM_MODEL_PATH must be set when installing the OpenVINO profile."
        )
    configured = {
        "OCR_BACKEND": backend.value,
        "OCR_MLX_MODEL": environ.get("OCR_MLX_MODEL", DEFAULT_MLX_MODEL),
        "OCR_MLX_SERVER_URL": environ.get("OCR_MLX_SERVER_URL", ""),
        "OCR_VL_CONCURRENCY": environ.get("OCR_VL_CONCURRENCY", ""),
        "OCR_VLM_MODEL_PATH": vlm_model_path,
        "OCR_LAYOUT_MODEL_PATH": environ.get("OCR_LAYOUT_MODEL_PATH", ""),
        "OCR_VLM_DEVICE": environ.get("OCR_VLM_DEVICE", "GPU"),
        "OCR_LAYOUT_DEVICE": environ.get("OCR_LAYOUT_DEVICE", "CPU"),
        "OCR_LLM_INT4_COMPRESS": environ.get("OCR_LLM_INT4_COMPRESS", "true"),
        "OCR_VISION_INT8_QUANT": environ.get("OCR_VISION_INT8_QUANT", "true"),
        "OCR_VLM_BATCH_SIZE": environ.get("OCR_VLM_BATCH_SIZE", "32"),
        "OCR_MAX_NEW_TOKENS": environ.get("OCR_MAX_NEW_TOKENS", "64"),
        "OCR_GPU_KV_CACHE_PRECISION": environ.get(
            "OCR_GPU_KV_CACHE_PRECISION", "f16"
        ),
        "OCR_MODEL_CACHE_DIR": environ.get("OCR_MODEL_CACHE_DIR", ""),
    }
    preserved = _read_unmanaged_lines(target, configured.keys())
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=".env.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        if preserved:
            temporary.write("\n".join(preserved).rstrip() + "\n")
        for key, value in configured.items():
            temporary.write(f"{key}={_quote(value)}\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(target)
    return target


def _read_unmanaged_lines(path: Path, managed_keys: Iterable[str]) -> list[str]:
    if not path.is_file():
        return []
    keys = set(managed_keys)
    preserved: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        key = line.split("=", maxsplit=1)[0].strip()
        if key not in keys:
            preserved.append(line)
    return preserved


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> None:
    """Write the selected installation profile to the user config directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=tuple(BackendKind), required=True)
    arguments = parser.parse_args()
    environment = {
        key: value
        for key, value in dotenv_values(Path.cwd() / ".env").items()
        if value is not None
    }
    environment.update(os.environ)
    try:
        target = write_install_config(
            BackendKind(arguments.backend), environment
        )
    except ValueError as error:
        parser.error(str(error))
    sys.stdout.write(f"Saved OCR defaults to {target}\n")


if __name__ == "__main__":
    main()
