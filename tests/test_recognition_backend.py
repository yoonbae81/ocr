from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

import adapters.recognition.backend as backend_module
from adapters.recognition.backend import OpenVinoBackendAdapter
from backend_config import OpenVinoBackendConfig


KV_PRECISION = "PADDLEOCR_VL_GPU_KV_CACHE_PRECISION"


def _create_model(model: Path) -> None:
    model.mkdir()
    for stem in ("llm_stateful_int4", "vision_int8", "llm_embd", "vision_mlp"):
        for suffix in ("xml", "bin"):
            (model / f"{stem}.{suffix}").touch()


def _install_fake_openvino(
    monkeypatch: pytest.MonkeyPatch, devices: tuple[str, ...]
) -> None:
    class FakeCore:
        available_devices = devices

    module = ModuleType("openvino")
    module.Core = FakeCore
    monkeypatch.setitem(sys.modules, "openvino", module)


def test_openvino_backend_is_lazy_and_restores_gpu_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model"
    _create_model(model)
    _install_fake_openvino(monkeypatch, ("CPU", "GPU.0"))
    created: list[OpenVinoBackendConfig] = []

    class FakeRecognizer:
        def __init__(self, config: OpenVinoBackendConfig) -> None:
            created.append(config)

    monkeypatch.setattr(
        backend_module, "OpenVinoPaddleRecognizerAdapter", FakeRecognizer
    )
    monkeypatch.setenv(KV_PRECISION, "original")
    config = OpenVinoBackendConfig(model, gpu_kv_cache_precision="f16")

    with OpenVinoBackendAdapter(config) as backend:
        assert created == []
        assert os.environ[KV_PRECISION] == "original"
        first = backend.get_recognizer()
        assert backend.get_recognizer() is first
        assert os.environ[KV_PRECISION] == "f16"

    assert len(created) == 1
    assert os.environ[KV_PRECISION] == "original"


def test_openvino_backend_rejects_unavailable_gpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "model"
    _create_model(model)
    _install_fake_openvino(monkeypatch, ("CPU",))

    with (
        OpenVinoBackendAdapter(OpenVinoBackendConfig(model)) as backend,
        pytest.raises(RuntimeError, match="available devices: CPU"),
    ):
        backend.get_recognizer()


def test_cache_namespace_tracks_semantics_but_not_batch_size(tmp_path: Path) -> None:
    model = tmp_path / "model"
    _create_model(model)
    baseline = OpenVinoBackendAdapter(OpenVinoBackendConfig(model))
    different_batch = OpenVinoBackendAdapter(
        OpenVinoBackendConfig(model, vlm_batch_size=8)
    )
    different_tokens = OpenVinoBackendAdapter(
        OpenVinoBackendConfig(model, max_new_tokens=128)
    )

    assert baseline.cache_namespace == different_batch.cache_namespace
    assert baseline.cache_namespace != different_tokens.cache_namespace
