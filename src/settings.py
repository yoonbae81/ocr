"""Layered runtime settings loaded from dotenv files and the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from backend_config import DEFAULT_MLX_MODEL, BackendKind


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """Defaults that CLI options may override."""

    backend: BackendKind = BackendKind.MLX
    model: str = DEFAULT_MLX_MODEL
    server_url: str | None = None
    vl_concurrency: int | None = None
    vlm_model_path: Path | None = None
    layout_model_path: Path | None = None
    vlm_device: str = "GPU"
    layout_device: str = "CPU"
    llm_int4_compress: bool = True
    vision_int8_quant: bool = True
    vlm_batch_size: int = 32
    max_new_tokens: int = 64
    gpu_kv_cache_precision: str = "f16"
    model_cache_dir: Path | None = None


def user_config_path(environ: Mapping[str, str] | None = None) -> Path:
    """Return the install-time dotenv location for the current platform."""
    values = os.environ if environ is None else environ
    explicit = values.get("OCR_CONFIG_FILE")
    if explicit:
        return Path(explicit).expanduser()
    app_data = values.get("APPDATA")
    if os.name == "nt" and app_data:
        return Path(app_data) / "ocr" / ".env"
    config_root = values.get("XDG_CONFIG_HOME")
    if config_root:
        return Path(config_root).expanduser() / "ocr" / ".env"
    return Path.home() / ".config" / "ocr" / ".env"


def load_settings(
    cwd: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    """Load user config, project config, then process environment overrides."""
    environment = dict(os.environ if environ is None else environ)
    working_directory = Path.cwd() if cwd is None else cwd
    installed_config = user_config_path(environment)
    project_config = working_directory / ".env"
    values: dict[str, str] = {}
    for path in (installed_config, project_config):
        if path.is_file():
            values.update(
                {
                    key: value
                    for key, value in dotenv_values(path).items()
                    if value is not None
                }
            )
    values.update(environment)
    try:
        backend = BackendKind(values.get("OCR_BACKEND", BackendKind.MLX))
    except ValueError as error:
        raise ValueError("OCR_BACKEND must be 'mlx' or 'openvino'.") from error
    return RuntimeSettings(
        backend=backend,
        model=values.get("OCR_MLX_MODEL", DEFAULT_MLX_MODEL),
        server_url=_optional(values.get("OCR_MLX_SERVER_URL")),
        vl_concurrency=_optional_int(values.get("OCR_VL_CONCURRENCY")),
        vlm_model_path=_optional_path(values.get("OCR_VLM_MODEL_PATH")),
        layout_model_path=_optional_path(values.get("OCR_LAYOUT_MODEL_PATH")),
        vlm_device=values.get("OCR_VLM_DEVICE", "GPU"),
        layout_device=values.get("OCR_LAYOUT_DEVICE", "CPU"),
        llm_int4_compress=_boolean(values.get("OCR_LLM_INT4_COMPRESS"), True),
        vision_int8_quant=_boolean(values.get("OCR_VISION_INT8_QUANT"), True),
        vlm_batch_size=_integer(values.get("OCR_VLM_BATCH_SIZE"), 32),
        max_new_tokens=_integer(values.get("OCR_MAX_NEW_TOKENS"), 64),
        gpu_kv_cache_precision=values.get(
            "OCR_GPU_KV_CACHE_PRECISION", "f16"
        ),
        model_cache_dir=_optional_path(values.get("OCR_MODEL_CACHE_DIR")),
    )


def _optional(value: str | None) -> str | None:
    return value or None


def _optional_path(value: str | None) -> Path | None:
    return None if not value else Path(value).expanduser()


def _optional_int(value: str | None) -> int | None:
    return None if not value else int(value)


def _integer(value: str | None, default: int) -> int:
    return default if not value else int(value)


def _boolean(value: str | None, default: bool) -> bool:
    if value is None or not value:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting: {value}")
