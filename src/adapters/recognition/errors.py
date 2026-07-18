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


@dataclass(slots=True)
class UnsupportedModelError(Exception):
    """Raised when the CLI model selector has no registered adapter."""

    model: str

    @override
    def __str__(self) -> str:
        return f"unsupported model: {self.model}"


@dataclass(slots=True)
class UnsupportedEffortError(Exception):
    """Raised when a selected recognizer cannot accept an effort setting."""

    model: str
    effort: str

    @override
    def __str__(self) -> str:
        return f"model {self.model} does not support effort: {self.effort}"
