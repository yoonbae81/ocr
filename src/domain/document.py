"""Document identity types."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Document:
    """A document selected from the current workspace."""

    path: Path

    @property
    def name(self) -> str:
        """Return the input file name without its extension."""
        return self.path.stem
