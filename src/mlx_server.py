"""Managed localhost MLX-VLM server for PaddleOCR-VL recognition."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Self
from urllib.error import URLError
from urllib.request import urlopen


@dataclass(slots=True)
class MlxServerAdapter:
    """Own the MLX-VLM process for one command execution."""

    model: str
    port: int | None = None
    _process: subprocess.Popen[str] | None = None

    def __enter__(self) -> Self:
        """Start the local server and wait until its OpenAI-compatible endpoint responds."""
        port = self.port or _available_port()
        self.port = port
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mlx_vlm.server",
                "--model",
                self.model,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                return_code = self._process.returncode
                self._process = None
                raise RuntimeError(
                    f"MLX-VLM server exited before becoming ready (code {return_code})."
                )
            try:
                with urlopen(f"{self.url}/v1/models", timeout=1):
                    return self
            except URLError:
                time.sleep(0.25)
        self.__exit__(None, None, None)
        raise RuntimeError("MLX-VLM server did not become ready within 120 seconds.")

    @property
    def url(self) -> str:
        """Return the local server base URL."""
        if self.port is None:
            raise RuntimeError("MLX-VLM server has not started.")
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *_: object) -> None:
        """Terminate the command-owned MLX server."""
        process = self._process
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            self._process = None


def _available_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
