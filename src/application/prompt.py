"""Workspace prompt selection for text-generating recognizers."""

from pathlib import Path
from typing import Final

DEFAULT_TRANSCRIPTION_PROMPT: Final = (
    "Transcribe only the visible page into Markdown. Preserve text, tables, "
    "formulas, and reading order. Return Markdown only; mark unreadable text "
    "as [UNREADABLE]."
)


def workspace_prompt_path(directory: Path) -> Path | None:
    """Return the closest applicable book or shared workspace prompt file."""
    local_prompt = directory / "prompt.md"
    if local_prompt.is_file():
        return local_prompt
    for parent in directory.parents:
        if parent.name != "workspace":
            continue
        shared_prompt = parent / "prompt.md"
        if shared_prompt.is_file():
            return shared_prompt
    return None
