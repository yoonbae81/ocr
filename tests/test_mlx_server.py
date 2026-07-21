from subprocess import TimeoutExpired

import pytest

from mlx_server import MlxServerAdapter


class StubbornProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.waits = 0

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        if self.waits == 1:
            if timeout is None:
                raise AssertionError
            raise TimeoutExpired("mlx-vlm", timeout)
        return 0


def test_server_exit_kills_process_that_ignores_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_waits = 2
    process = StubbornProcess()
    server = MlxServerAdapter("model")
    monkeypatch.setattr(server, "_process", process)

    server.__exit__(None, None, None)

    assert process.terminated
    assert process.killed
    assert process.waits == expected_waits
