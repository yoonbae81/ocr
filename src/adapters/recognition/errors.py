"""Recognition boundary errors."""

from dataclasses import dataclass
from typing import override


@dataclass(slots=True)
class RecognitionError(Exception):
    """Raised when a configured recognizer cannot return Markdown."""

    detail: str

    @override
    def __str__(self) -> str:
        return self.detail
