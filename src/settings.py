"""Configuration loaded from the repository-level environment file."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class MissingPaddleConfigurationError(Exception):
    """Identify required PaddleOCR environment fields that are not configured."""

    fields: tuple[str, ...]

    @override
    def __str__(self) -> str:
        return f"{', '.join(self.fields)} required"


class Settings(BaseSettings):
    """Model configuration shared by the command composition root."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    paddle_endpoint: str = ""
    paddle_model: str = ""
    concurrency: int = Field(default=5, ge=1)
    recognition_timeout: float = Field(default=300.0, ge=1.0)

    def validate_paddle_configuration(self) -> None:
        """Reject missing PaddleOCR configuration."""
        fields = tuple(
            field
            for field, value in (
                ("PADDLE_ENDPOINT", self.paddle_endpoint),
                ("PADDLE_MODEL", self.paddle_model),
            )
            if not value
        )
        if fields:
            raise MissingPaddleConfigurationError(fields=fields)
