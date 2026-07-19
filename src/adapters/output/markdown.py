"""Markdown output adapter for physical source pages."""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import final, override

from adapters.output.postprocessors import (
    DEFAULT_RULE_DIRECTORY,
    RegexReplacement,
    load_regex_rules,
)
from application.ports.output import DocumentOutputPort, OutputResult
from domain.content import PageContent, PageNumber
from domain.errors import UnsafeOutputPathError
from domain.status import PageFailure, ProcessingStatus

_STATUS_HEADING = re.compile(
    r"^## (?P<name>Document|Completed|Failed)\s*$", re.MULTILINE
)


@final
class MarkdownOutput(DocumentOutputPort):
    """Persist each recognized physical page as one Markdown file."""

    def __init__(
        self,
        directory: Path,
        *,
        rule_directory: Path = DEFAULT_RULE_DIRECTORY,
    ) -> None:
        """Set the directory where page files and processing state are written."""
        if directory.is_symlink():
            raise UnsafeOutputPathError(directory)
        self._directory = directory
        self._rules = load_regex_rules(rule_directory)

    @override
    def write(
        self,
        pages: tuple[PageContent, ...],
        status: ProcessingStatus,
        *,
        source_name: str,
    ) -> OutputResult:
        """Atomically write successful pages and the state describing this attempt."""
        files: list[Path] = []
        for page in pages:
            path = self._directory / _page_filename(page.page)
            _write_atomically(path, _render_page(page, source_name, self._rules))
            files.append(path)
        status_path = self._directory / "status.md"
        _write_atomically(status_path, _render_status(status))
        files.append(status_path)
        return OutputResult(files=tuple(files))

    def load_status(self, *, document: str | None = None) -> ProcessingStatus:
        """Return state only when it belongs to the requested input document."""
        path = self._directory / "status.md"
        if not path.exists():
            return ProcessingStatus(document=document)
        status = _parse_status(path.read_text(encoding="utf-8"))
        return (
            status
            if document is None or status.document == document
            else ProcessingStatus(document=document)
        )


def _page_filename(page: PageNumber) -> str:
    return f"{page:04d}.md"


def _render_page(
    page: PageContent,
    source_name: str,
    rules: tuple[RegexReplacement, ...],
) -> str:
    body = page.body
    for rule in rules:
        body = rule.apply(body)
    normalized_body = body.rstrip("\n")
    return (
        f"---\nsource: {json.dumps(source_name, ensure_ascii=False)}\n"
        f"page: {page.page}\n---\n\n{normalized_body}\n"
    )


def _render_status(status: ProcessingStatus) -> str:
    completed = "\n".join(f"- {page}" for page in status.completed) or "- none"
    failures = (
        "\n".join(f"- {failure.page}: {failure.reason}" for failure in status.failures)
        or "- none"
    )
    return (
        f"# Status\n\n## Document\n{status.document or '- none'}"
        f"\n\n## Completed\n{completed}\n\n## Failed\n{failures}\n"
    )


def _parse_status(content: str) -> ProcessingStatus:
    document_lines = tuple(
        line
        for body in _status_section_bodies(content, "Document")
        for line in body.splitlines()
        if line and not line.startswith("- ")
    )
    completed = tuple(
        PageNumber(int(item))
        for body in _status_section_bodies(content, "Completed")
        for line in body.splitlines()
        if line.startswith("- ") and (item := line[2:]).isdecimal()
    )
    failures = tuple(
        failure
        for body in _status_section_bodies(content, "Failed")
        for line in body.splitlines()
        if line.startswith("- ")
        if (failure := _parse_failure(line[2:])) is not None
    )
    return ProcessingStatus(
        document=document_lines[-1] if document_lines else None,
        completed=completed,
        failures=failures,
    )


def _status_section_bodies(content: str, name: str) -> tuple[str, ...]:
    headings = tuple(_STATUS_HEADING.finditer(content))
    return tuple(
        content[heading.end() : headings[index + 1].start()]
        if index + 1 < len(headings)
        else content[heading.end() :]
        for index, heading in enumerate(headings)
        if heading.group("name") == name
    )


def _parse_failure(item: str) -> PageFailure | None:
    page, separator, reason = item.partition(": ")
    if not separator or not page.isdecimal():
        return None
    return PageFailure(page=PageNumber(int(page)), reason=reason)


def _write_atomically(path: Path, content: str) -> None:
    _assert_no_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        _ = temporary_file.write(content)
    _ = temporary_path.replace(path)


def _assert_no_symlink(path: Path) -> None:
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise UnsafeOutputPathError(path)
        current = current.parent
