"""Codex CLI recognition adapter."""

from dataclasses import dataclass

from domain.content import ImagePage

from ._cli import run_command, temporary_image


@dataclass(frozen=True, slots=True)
class CodexAdapter:
    """Recognize images through the installed Codex CLI."""

    model: str
    effort: str
    timeout: float = 300.0

    def recognize(self, page: ImagePage, prompt: str) -> str:
        """Send one materialized page and its caller-provided prompt to Codex."""
        with temporary_image(page) as image_path:
            command = (
                "codex",
                "exec",
                "-i",
                str(image_path),
                "--model",
                self.model,
                "-c",
                f'model_reasoning_effort="{self.effort}"',
                prompt,
            )
            return run_command(command, timeout=self.timeout, cwd=image_path.parent)
