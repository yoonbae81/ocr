"""Managed recognition-backend adapters."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
from types import TracebackType
from typing import Self

from adapters.recognition.mlx import MlxPaddleRecognizerAdapter
from adapters.recognition.openvino import OpenVinoPaddleRecognizerAdapter
from backend_config import MlxBackendConfig, OpenVinoBackendConfig
from mlx_server import MlxServerAdapter
from ports import PageRecognizer


Reporter = Callable[[str], None]


def _ignore_message(_: str) -> None:
    return None


class MlxBackendAdapter:
    """Own an optional MLX server and lazily create its Paddle client."""

    def __init__(
        self,
        config: MlxBackendConfig,
        reporter: Reporter = _ignore_message,
    ) -> None:
        self._config = config
        self._report = reporter
        self._resources = ExitStack()
        self._recognizer: PageRecognizer | None = None

    @property
    def cache_namespace(self) -> str:
        """Identify MLX results independently from other runtimes."""
        return f"mlx:{self._config.model}:schema=v1"

    def __enter__(self) -> Self:
        return self

    def get_recognizer(self) -> PageRecognizer:
        """Start the local service only when recognition is actually required."""
        if self._recognizer is not None:
            return self._recognizer
        url = self._config.server_url
        if url is None:
            self._report(f"Starting local MLX-VLM server: {self._config.model}")
            url = self._resources.enter_context(
                MlxServerAdapter(self._config.model)
            ).url
        else:
            self._report(f"Using external MLX-VLM server: {url}")
        self._report("Initializing MLX OCR recognizer...")
        self._recognizer = MlxPaddleRecognizerAdapter(
            url,
            self._config.model,
            max_concurrency=self._config.max_concurrency,
        )
        self._report("MLX OCR recognizer ready.")
        return self._recognizer

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._recognizer = None
        self._resources.__exit__(exc_type, exc_value, traceback)


class OpenVinoBackendAdapter:
    """Own one in-process OpenVINO pipeline and its process-scoped settings."""

    _KV_ENVIRONMENT_VARIABLE = "PADDLEOCR_VL_GPU_KV_CACHE_PRECISION"

    def __init__(
        self,
        config: OpenVinoBackendConfig,
        reporter: Reporter = _ignore_message,
    ) -> None:
        self._config = config
        self._report = reporter
        self._recognizer: PageRecognizer | None = None
        self._previous_kv_precision: str | None = None
        self._environment_configured = False

    @property
    def cache_namespace(self) -> str:
        """Fingerprint every setting that may change recognized content."""
        payload = {
            "backend": "openvino",
            "schema": 1,
            "vlm_model": _path_identity(self._config.vlm_model_path),
            "layout_model": (
                None
                if self._config.layout_model_path is None
                else _path_identity(self._config.layout_model_path)
            ),
            "vlm_device": self._config.vlm_device.upper(),
            "layout_device": self._config.layout_device.upper(),
            "llm_int4": self._config.llm_int4_compress,
            "vision_int8": self._config.vision_int8_quant,
            "max_new_tokens": self._config.max_new_tokens,
            "gpu_kv_cache_precision": self._config.gpu_kv_cache_precision,
        }
        digest = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        return f"openvino:paddleocr-vl:{digest}"

    def __enter__(self) -> Self:
        return self

    def get_recognizer(self) -> PageRecognizer:
        """Compile the OpenVINO pipeline only after the first cache miss."""
        if self._recognizer is None:
            self._validate_model_paths()
            self._validate_device()
            self._configure_environment()
            self._report(
                "Initializing OpenVINO OCR recognizer "
                f"(VLM={self._config.vlm_device}, "
                f"layout={self._config.layout_device})..."
            )
            self._recognizer = OpenVinoPaddleRecognizerAdapter(self._config)
            self._report("OpenVINO OCR recognizer ready.")
        return self._recognizer

    def __exit__(self, *_: object) -> None:
        self._recognizer = None
        if not self._environment_configured:
            return
        if self._previous_kv_precision is None:
            os.environ.pop(self._KV_ENVIRONMENT_VARIABLE, None)
        else:
            os.environ[self._KV_ENVIRONMENT_VARIABLE] = self._previous_kv_precision

    def _configure_environment(self) -> None:
        if self._environment_configured or not self._config.vlm_device.upper().startswith(
            "GPU"
        ):
            return
        self._previous_kv_precision = os.environ.get(self._KV_ENVIRONMENT_VARIABLE)
        os.environ[self._KV_ENVIRONMENT_VARIABLE] = (
            self._config.gpu_kv_cache_precision
        )
        self._environment_configured = True

    def _validate_model_paths(self) -> None:
        model = self._config.vlm_model_path
        if not model.is_dir():
            raise ValueError(f"OpenVINO VLM model directory does not exist: {model}")
        required_stems = [
            "llm_stateful_int4"
            if self._config.llm_int4_compress
            else "llm_stateful",
            "vision_int8" if self._config.vision_int8_quant else "vision",
            "llm_embd",
            "vision_mlp",
        ]
        missing = [
            f"{stem}.{suffix}"
            for stem in required_stems
            for suffix in ("xml", "bin")
            if not (model / f"{stem}.{suffix}").is_file()
        ]
        if missing:
            raise ValueError(
                "OpenVINO VLM model is incomplete; missing: " + ", ".join(missing)
            )
        layout = self._config.layout_model_path
        if layout is not None and not layout.is_file():
            raise ValueError(f"OpenVINO layout model does not exist: {layout}")

    def _validate_device(self) -> None:
        try:
            import openvino as ov  # pyright: ignore[reportMissingImports]
        except ImportError as error:
            raise RuntimeError(
                "OpenVINO backend dependencies are not installed; "
                "install the project with the 'openvino' extra."
            ) from error
        available = tuple(device.upper() for device in ov.Core().available_devices)
        for configured in (self._config.vlm_device, self._config.layout_device):
            requested = configured.upper()
            if requested == "AUTO":
                continue
            if not any(
                device == requested or device.startswith(f"{requested}.")
                for device in available
            ):
                choices = ", ".join(available) or "none"
                raise RuntimeError(
                    f"OpenVINO device {configured!r} is unavailable; "
                    f"available devices: {choices}."
                )


def _path_identity(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    if resolved.is_file():
        stat = resolved.stat()
        return {
            "path": str(resolved),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    files: list[tuple[str, int, int]] = []
    if resolved.is_dir():
        for child in sorted(resolved.iterdir()):
            if child.is_file() and child.suffix.lower() in {".xml", ".bin", ".json"}:
                stat = child.stat()
                files.append((child.name, stat.st_size, stat.st_mtime_ns))
    return {"path": str(resolved), "files": files}
