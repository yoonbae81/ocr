from __future__ import annotations

import re
from itertools import chain
from pathlib import Path
from typing import Final

from PIL import Image

from domain import PageMarkdown, PageNumber, SourcePage

_TABLE_CELL_PATTERN: Final = re.compile(
    r"(<t[dh]\b[^>]*>)(.*?)(</t[dh]>)", re.DOTALL | re.IGNORECASE
)
_CENTERED_IMAGE_PATTERN: Final = re.compile(
    r'<div\b[^>]*>\s*<img\s+src="(?P<src>[^"]+)"\s+'
    r'alt="(?P<alt>[^"]*)"[^>]*/?>\s*</div>',
    re.IGNORECASE,
)
_CROP_SOURCE_PATTERN: Final = re.compile(
    r"img_in_image_box_(?P<start_x>\d+)_(?P<start_y>\d+)_"
    r"(?P<end_x>\d+)_(?P<end_y>\d+)\.(?:jpe?g|png|webp)$",
    re.IGNORECASE,
)
_RULES_DIR: Final = Path(__file__).with_name("rules") / "markdown"
_RULE_PATHS: Final = tuple(sorted(_RULES_DIR.glob("*.txt")))
_RULE_LINE_PARTS: Final = 2


def _load_regex_rules(path: Path) -> tuple[tuple[re.Pattern[str], str], ...]:
    loaded: list[tuple[re.Pattern[str], str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", maxsplit=1)
        if len(parts) != _RULE_LINE_PARTS:
            continue
        pattern, replacement = parts
        loaded.append((re.compile(pattern), replacement))
    return tuple(loaded)


_REGEX_RULES: Final = tuple(
    chain.from_iterable(_load_regex_rules(path) for path in _RULE_PATHS)
)


def normalize_markdown(result: PageMarkdown, image_directory: Path) -> str:
    normalized = _normalize_table_breaks(result.text)
    normalized = _normalize_images(normalized, result.page, image_directory)
    return _apply_regex_rules(normalized, _REGEX_RULES)


def _normalize_table_breaks(text: str) -> str:
    return _TABLE_CELL_PATTERN.sub(_replace_table_cell, text)


def _normalize_images(text: str, page: SourcePage, image_directory: Path) -> str:
    has_crop = any(
        _CROP_SOURCE_PATTERN.search(match.group("src"))
        for match in _CENTERED_IMAGE_PATTERN.finditer(text)
    )
    if not has_crop:
        return _CENTERED_IMAGE_PATTERN.sub(_replace_image_reference, text)
    image_directory.mkdir(parents=True, exist_ok=True)
    with Image.open(page.image_path) as source_image:
        return _CENTERED_IMAGE_PATTERN.sub(
            lambda match: _replace_image(match, page, image_directory, source_image),
            text,
        )


def _apply_regex_rules(
    text: str, rules: tuple[tuple[re.Pattern[str], str], ...]
) -> str:
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def _replace_table_cell(match: re.Match[str]) -> str:
    content = match.group(2).replace("\\n", "<br/>").replace("\n", "<br/>")
    return f"{match.group(1)}{content}{match.group(3)}"


def _replace_image_reference(match: re.Match[str]) -> str:
    return f"![{match.group('alt')}]({match.group('src')})"


def _replace_image(
    match: re.Match[str],
    page: SourcePage,
    image_directory: Path,
    source_image: Image.Image,
) -> str:
    coordinates = _CROP_SOURCE_PATTERN.search(match.group("src"))
    if coordinates is None:
        return _replace_image_reference(match)
    start_x = int(coordinates.group("start_x"))
    start_y = int(coordinates.group("start_y"))
    end_x = int(coordinates.group("end_x"))
    end_y = int(coordinates.group("end_y"))
    image_name = f"{page.number.value}_{start_x}_{start_y}_{end_x}_{end_y}.jpg"
    source_image.crop((start_x, start_y, end_x, end_y)).convert("RGB").save(
        image_directory / image_name, "JPEG", quality=95
    )
    return f"![{match.group('alt')}](img/{image_name})"


class MarkdownPageExporter:

    def is_exported(self, page: PageNumber, destination: Path) -> bool:
        return (destination / f"{page.value}.md").exists()

    def export(self, result: PageMarkdown, destination: Path, replace: bool) -> None:
        markdown_path = destination / f"{result.page.number.value}.md"
        if markdown_path.exists() and not replace:
            raise FileExistsError(f"Output exists; pass --replace: {markdown_path}")
        destination.mkdir(parents=True, exist_ok=True)
        image_directory = destination / "img"
        markdown_path.write_text(
            normalize_markdown(result, image_directory).strip() + "\n",
            encoding="utf-8",
        )
