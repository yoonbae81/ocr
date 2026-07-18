"""Agy CLI recognition adapter."""

from dataclasses import dataclass

from domain.content import ImagePage

from ._cli import run_command, temporary_image


@dataclass(frozen=True, slots=True)
class AgyAdapter:
    """Recognize images through the installed Agy CLI."""

    model: str
    timeout: float = 300.0

    def recognize(self, page: ImagePage, prompt: str) -> str:
        """Send one materialized page and its caller-provided prompt to Agy."""
        with temporary_image(page) as image_path:
            command = (
                "agy",
                "--model",
                self.model,
                "--print",
                f"Read the image file at {image_path} and transcribe it.\n\n{prompt}",
            )
            return run_command(command, timeout=self.timeout, cwd=image_path.parent)
