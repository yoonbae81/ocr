"""Markdown document output adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, final, override
from unicodedata import normalize

from adapters.output.postprocessors import (
    DEFAULT_RULE_DIRECTORY,
    RegexReplacement,
    load_regex_rules,
)
from application.ports.output import DocumentOutputPort, OutputResult
from domain.content import PageNumber
from domain.errors import UnsafeOutputPathError
from domain.status import PageFailure, ProcessingStatus

if TYPE_CHECKING:
    from domain.content import DocumentBundle, DocumentGroup, PageContent


_STATUS_HEADING = re.compile(
    r"^## (?P<name>Document|Completed|Failed|Current Chapter)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class _ArtifactCollisionError(ValueError):
    @override
    def __str__(self) -> str:
        return "document groups resolve to the same output artifact"


_PAGE_MARKER_LINE = re.compile(r"^<!-- page: \d+ -->$")
_SOURCE_MARKER_LINE = re.compile(r"^<!-- source: .+ -->$")


@final
class MarkdownOutput(DocumentOutputPort):
    """Persist document bundles as Markdown artifacts in one output directory."""

    def __init__(
        self,
        directory: Path,
        *,
        rule_directory: Path = DEFAULT_RULE_DIRECTORY,
    ) -> None:
        """Set the directory where this output format writes its artifacts."""
        if directory.is_symlink():
            raise UnsafeOutputPathError(directory)
        self._directory: Path = directory
        self._rules: tuple[RegexReplacement, ...] = load_regex_rules(rule_directory)

    @override
    def write(
        self,
        bundle: DocumentBundle,
        status: ProcessingStatus,
    ) -> OutputResult:
        """Write all group artifacts and the current processing status atomically."""
        files: list[Path] = []
        groups = tuple(group for group in bundle.groups if group.pages)
        paths = tuple(self._directory / _artifact_name(group) for group in groups)
        if len(paths) != len(set(paths)):
            raise _ArtifactCollisionError
        for group, path in zip(groups, paths, strict=True):
            rendered = _render_group(group, self._rules)
            if group.name.isdecimal():
                _write_atomically(path, rendered)
            else:
                _merge_blocks_atomically(path, rendered)
            files.append(path)
        status_path = self._directory / "status.md"
        _write_atomically(status_path, _render_status(status))
        files.append(status_path)
        return OutputResult(files=tuple(files))

    def load_status(self, *, document: str | None = None) -> ProcessingStatus:
        """Return the previously persisted processing state when available."""
        path = self._directory / "status.md"
        if not path.exists():
            return ProcessingStatus()
        status = _parse_status(path.read_text(encoding="utf-8"))
        if document is not None and status.document != document:
            return ProcessingStatus(document=document)
        return status


def _artifact_name(group: DocumentGroup) -> Path:
    if group.name.isdecimal():
        return Path(f"{int(group.name)}.md")
    if group.name == "book":
        return Path("book.md")
    artifact = Path(f"{_safe_name(group.name)}.md")
    return Path(_safe_name(group.parent)) / artifact if group.parent else artifact


def _safe_name(name: str) -> str:
    normalized = normalize("NFKC", name)
    tokens = "".join(
        character if character.isalnum() or character.isspace() else ""
        for character in normalized
    )
    return " ".join(tokens.split()) or "untitled"


def _render_group(
    group: DocumentGroup,
    rules: tuple[RegexReplacement, ...],
) -> str:
    return "\n\n".join(_render_page(page, rules) for page in group.pages)


def _render_page(
    page: PageContent,
    rules: tuple[RegexReplacement, ...],
) -> str:
    body = page.body
    for rule in rules:
        body = rule.apply(body)
    body = "\n".join(_escape_control_marker(line) for line in body.splitlines())
    return f"<!-- page: {page.page} -->\n\n{body}\n"


def _escape_control_marker(line: str) -> str:
    if _PAGE_MARKER_LINE.fullmatch(line) or _SOURCE_MARKER_LINE.fullmatch(line):
        return f"\\{line}"
    return line


def _render_status(status: ProcessingStatus) -> str:
    completed = "\n".join(f"- {page}" for page in status.completed) or "- none"
    failures = (
        "\n".join(f"- {failure.page}: {failure.reason}" for failure in status.failures)
        or "- none"
    )
    current_chapter = status.current_chapter or "- none"
    return (
        f"# Status\n\n## Document\n{status.document or '- none'}"
        f"\n\n## Completed\n{completed}\n\n## Failed\n{failures}"
        f"\n\n## Current Chapter\n{current_chapter}\n"
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
    chapter_lines = tuple(
        line
        for body in _status_section_bodies(content, "Current Chapter")
        for line in body.splitlines()
        if line and not line.startswith("- ")
    )
    return ProcessingStatus(
        document=document_lines[-1] if document_lines else None,
        completed=completed,
        failures=failures,
        current_chapter=chapter_lines[-1] if chapter_lines else None,
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


def _merge_blocks_atomically(path: Path, content: str) -> None:
    _assert_no_symlink(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_blocks = _rendered_page_blocks(existing)
    if existing and not existing_blocks:
        separator = "\n\n" if existing else ""
        _write_atomically(path, f"{existing.rstrip()}{separator}{content.lstrip()}")
        return
    merged = existing_blocks | _rendered_page_blocks(content)
    ordered = "\n\n".join(merged[page] for page in sorted(merged))
    _write_atomically(path, f"{ordered}\n")


def _assert_no_symlink(path: Path) -> None:
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise UnsafeOutputPathError(path)
        current = current.parent


def _rendered_page_blocks(content: str) -> dict[PageNumber, str]:
    lines = content.splitlines()
    starts = tuple(
        (index, page)
        for index, line in enumerate(lines)
        if (page := _page_marker(line)) is not None
    )
    blocks: dict[PageNumber, str] = {}
    for position, (start, page) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        blocks[page] = "\n".join(
            line for line in lines[start:end] if not _source_marker(line)
        ).strip()
    return blocks


def _source_marker(line: str) -> bool:
    return line.startswith("<!-- source: ") and line.endswith(" -->")


def _page_marker(line: str) -> PageNumber | None:
    prefix = "<!-- page: "
    suffix = " -->"
    if not line.startswith(prefix) or not line.endswith(suffix):
        return None
    value = line.removeprefix(prefix).removesuffix(suffix)
    return PageNumber(int(value)) if value.isdecimal() else None
