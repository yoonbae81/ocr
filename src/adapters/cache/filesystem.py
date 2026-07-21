"""Filesystem cache for raw page-recognition results."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from domain import PageMarkdown, SourcePage


@dataclass(frozen=True, slots=True)
class FilesystemRecognitionCache:
    """Store raw Markdown by rendered-page and recognizer fingerprints."""

    root: Path
    namespace: str

    def load(self, page: SourcePage) -> PageMarkdown | None:
        """Return cached raw Markdown for an identical rendered page."""
        cache_path = self._path(page)
        if not cache_path.exists():
            return None
        return PageMarkdown(page, cache_path.read_text(encoding="utf-8"))

    def store(self, result: PageMarkdown) -> None:
        """Atomically store raw Markdown for later output-format processing."""
        self.root.mkdir(parents=True, exist_ok=True)
        cache_path = self._path(result.page)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.root,
            prefix=f"{cache_path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(result.text)
            temporary_path = Path(temporary.name)
        temporary_path.replace(cache_path)

    def _path(self, page: SourcePage) -> Path:
        digest = sha256(self.namespace.encode())
        with page.image_path.open("rb") as image:
            while chunk := image.read(1024 * 1024):
                digest.update(chunk)
        return self.root / f"{digest.hexdigest()}.md"
