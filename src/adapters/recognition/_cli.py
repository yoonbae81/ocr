"""Shared local CLI recognition support."""

import subprocess
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from domain.content import ImagePage

from .errors import RecognitionError

_COMMAND_NOT_FOUND: Final = "command not found: {command}"
_RECOGNITION_TIMEOUT: Final = "recognition timed out after {timeout:g} seconds"
_COMMAND_FAILED: Final = "recognition command failed"
_EMPTY_CONTENT: Final = "recognition command returned empty content"
_UNSUPPORTED_MEDIA_TYPE: Final = "unsupported image media type: {media_type}"


def run_command(command: Sequence[str], *, timeout: float, cwd: Path) -> str:
    """Run a local model command and return its nonempty standard output."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, shell disabled
            command,
            capture_output=True,
            check=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError as error:
        raise RecognitionError(
            detail=_COMMAND_NOT_FOUND.format(command=command[0])
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RecognitionError(
            detail=_RECOGNITION_TIMEOUT.format(timeout=timeout)
        ) from error
    except subprocess.CalledProcessError as error:
        raise RecognitionError(detail=_COMMAND_FAILED) from error

    output = result.stdout.strip()
    if not output:
        raise RecognitionError(detail=_EMPTY_CONTENT)
    return output


@contextmanager
def temporary_image(page: ImagePage) -> Generator[Path, None, None]:  # noqa: UP043
    """Materialize a page image with the suffix expected by local model CLIs."""
    suffix = image_suffix(page.media_type)
    with tempfile.TemporaryDirectory(prefix="ocr-") as directory:
        path = Path(directory) / f"page-{page.page}{suffix}"
        _ = path.write_bytes(page.image)
        yield path


def image_suffix(media_type: str) -> str:
    """Map supported image media types to a file suffix."""
    match media_type:
        case "image/jpeg":
            return ".jpg"
        case "image/png":
            return ".png"
        case unsupported:
            raise RecognitionError(
                detail=_UNSUPPORTED_MEDIA_TYPE.format(media_type=unsupported)
            )
