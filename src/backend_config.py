"""Backend-specific configuration values used at the composition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


DEFAULT_MLX_MODEL = "matrixmaven/PaddleOCR-VL-1.6-MLX"


class BackendKind(StrEnum):
    """Supported local recognition implementations."""

    MLX = "mlx"
    OPENVINO = "openvino"


@dataclass(frozen=True, slots=True)
class MlxBackendConfig:
    """Settings for the MLX-VLM service-backed recognizer."""

    model: str = DEFAULT_MLX_MODEL
    server_url: str | None = None
    max_concurrency: int | None = None


@dataclass(frozen=True, slots=True)
class OpenVinoBackendConfig:
    """Settings for the in-process OpenVINO recognizer."""

    vlm_model_path: Path
    layout_model_path: Path | None = None
    vlm_device: str = "GPU"
    layout_device: str = "CPU"
    llm_int4_compress: bool = True
    vision_int8_quant: bool = True
    vlm_batch_size: int = 32
    max_new_tokens: int = 64
    gpu_kv_cache_precision: str = "f16"
    model_cache_dir: Path | None = None
