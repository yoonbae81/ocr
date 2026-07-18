"""Load the user-authored chapter map from toc.md."""

import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Final, override

from domain.chapters import ChapterBoundary, ChapterMap, PartBoundary
from domain.content import PageNumber

_PAGE = re.compile(r"^\s*-\s+page:\s*(?P<page>\d+)\s*$", re.MULTILINE)
_TITLE = re.compile(r"^\s+title:\s*(?P<title>.+?)\s*$", re.MULTILINE)
_CONTENTS_HEADINGS: Final = frozenset({"Contents", "Chapters"})
_SECTION_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_GROUP_HEADING = re.compile(r"^(?P<title>.+?)\s*\|\s*page:\s*(?P<page>\d+)$")
_ITEM_HEADING = re.compile(
    r"^###\s+(?P<title>.+?)\s*\|\s*page:\s*(?P<page>\d+)\s*$",
    re.MULTILINE,
)
_MISSING_TOC: Final = "toc.md is required for --group chapter"
_EMPTY_TOC: Final = "toc.md has no chapters"
_INVALID_ENTRY: Final = "toc.md chapter entries require positive page and title fields"
_UNSORTED_TOC: Final = "toc.md chapter pages must be ascending"


class ChapterMapUnavailableError(Exception):
    """Indicate that toc.md cannot provide chapter boundaries."""

    def __init__(self, message: str = "chapter map unavailable") -> None:
        """Create an error with the user-facing reason for the unavailable map."""
        super().__init__(message)
        self.message: str = message

    @override
    def __str__(self) -> str:
        """Return the user-facing reason."""
        return self.message


@dataclass(frozen=True, slots=True)
class _Section:
    heading: str | None
    body: str
    body_position: int


@dataclass(frozen=True, slots=True)
class _LocatedBoundary:
    position: int
    boundary: ChapterBoundary


def load_chapter_map(path: Path, offset: int = 0) -> ChapterMap:
    """Parse source-page chapter starts from printed TOC pages plus an offset."""
    if not path.is_file():
        raise ChapterMapUnavailableError(_MISSING_TOC)

    located: list[_LocatedBoundary] = []
    parts: list[PartBoundary] = []
    for section in _sections(path.read_text(encoding="utf-8")):
        section_boundaries, part = _parse_section(section, offset)
        located.extend(section_boundaries)
        if part is not None:
            parts.append(part)

    boundaries = tuple(
        item.boundary for item in sorted(located, key=lambda item: item.position)
    )
    if not boundaries:
        raise ChapterMapUnavailableError(_EMPTY_TOC)
    _validate_boundary_order(boundaries)
    return ChapterMap(boundaries=boundaries, parts=tuple(parts))


def _sections(content: str) -> tuple[_Section, ...]:
    headings = tuple(_SECTION_HEADING.finditer(content))
    sections: list[_Section] = []
    first_heading = headings[0].start() if headings else len(content)
    if preamble := content[:first_heading]:
        sections.append(_Section(heading=None, body=preamble, body_position=0))
    for index, heading in enumerate(headings):
        body_start = heading.end()
        body_end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(content)
        )
        sections.append(
            _Section(
                heading=heading.group("title").strip(),
                body=content[body_start:body_end],
                body_position=body_start,
            )
        )
    return tuple(sections)


def _parse_section(
    section: _Section,
    offset: int,
) -> tuple[tuple[_LocatedBoundary, ...], PartBoundary | None]:
    group_match = (
        _GROUP_HEADING.fullmatch(section.heading)
        if section.heading is not None
        else None
    )
    if group_match is not None:
        part = group_match.group("title").strip()
        part_boundary = PartBoundary(
            page=PageNumber(int(group_match.group("page")) + offset),
            title=part,
        )
        return _parse_chapter_body(section, offset, part), part_boundary
    if section.heading in _CONTENTS_HEADINGS:
        return _parse_chapter_body(section, offset, None), None
    return _parse_heading_entries(section, offset, None), None


def _parse_chapter_body(
    section: _Section,
    offset: int,
    part: str | None,
) -> tuple[_LocatedBoundary, ...]:
    first_heading = _ITEM_HEADING.search(section.body)
    list_body = section.body[: first_heading.start()] if first_heading else section.body
    return (
        *_parse_list_entries(list_body, section.body_position, offset, part),
        *_parse_heading_entries(section, offset, part),
    )


def _parse_heading_entries(
    section: _Section,
    offset: int,
    part: str | None,
) -> tuple[_LocatedBoundary, ...]:
    return tuple(
        _LocatedBoundary(
            position=section.body_position + match.start(),
            boundary=_boundary(
                page=int(match.group("page")) + offset,
                title=match.group("title").strip(),
                part=part,
            ),
        )
        for match in _ITEM_HEADING.finditer(section.body)
    )


def _parse_list_entries(
    body: str,
    body_position: int,
    offset: int,
    part: str | None,
) -> tuple[_LocatedBoundary, ...]:
    page_matches = tuple(_PAGE.finditer(body))
    entries: list[_LocatedBoundary] = []
    for index, page_match in enumerate(page_matches):
        entry_end = (
            page_matches[index + 1].start()
            if index + 1 < len(page_matches)
            else len(body)
        )
        title_match = _TITLE.search(body, page_match.end(), entry_end)
        entries.append(
            _LocatedBoundary(
                position=body_position + page_match.start(),
                boundary=_boundary(
                    page=int(page_match.group("page")) + offset,
                    title=title_match.group("title").strip() if title_match else None,
                    part=part,
                ),
            )
        )
    return tuple(entries)


def _boundary(page: int, title: str | None, part: str | None) -> ChapterBoundary:
    if title is None or page < 1:
        raise ChapterMapUnavailableError(_INVALID_ENTRY)
    return ChapterBoundary(page=PageNumber(page), title=title, part=part)


def _validate_boundary_order(boundaries: tuple[ChapterBoundary, ...]) -> None:
    if any(current.page < previous.page for previous, current in pairwise(boundaries)):
        raise ChapterMapUnavailableError(_UNSORTED_TOC)
