"""Composition root for recognition backend adapters."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from adapters.recognition.backend import MlxBackendAdapter, OpenVinoBackendAdapter
from backend_config import MlxBackendConfig, OpenVinoBackendConfig
from ports import RecognitionBackend


BackendConfig = MlxBackendConfig | OpenVinoBackendConfig


@contextmanager
def open_backend(
    config: BackendConfig,
    reporter: Callable[[str], None],
) -> Iterator[RecognitionBackend]:
    """Create and close the adapter selected at the inbound boundary."""
    if isinstance(config, MlxBackendConfig):
        with MlxBackendAdapter(config, reporter) as backend:
            yield backend
        return
    with OpenVinoBackendAdapter(config, reporter) as backend:
        yield backend
