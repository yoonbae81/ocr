"""Configuration loaded from the repository-level environment file."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, override

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelName(StrEnum):
    """Recognition adapters selectable from the terminal."""

    GPT = "gpt"
    GEMINI = "gemini"
    PADDLE = "paddle"


@dataclass(frozen=True, slots=True)
class MissingModelConfigurationError(Exception):
    """Identify environment fields required by one selected recognizer."""

    model: ModelName
    fields: tuple[str, ...]

    @override
    def __str__(self) -> str:
        return f"{', '.join(self.fields)} required for model {self.model.value}"


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
    codex_model: str = ""
    agy_model: str = ""
    default_model: ModelName = ModelName.GPT
    concurrency: int = Field(default=1, ge=1)
    recognition_timeout: float = Field(default=300.0, ge=1.0)

    @field_validator("default_model", mode="before")
    @classmethod
    def normalize_default_model(cls, value: str) -> str:
        """Normalize environment-provided model selectors before enum parsing."""
        return value.lower()

    def validate_for_model(self, model: ModelName) -> None:
        """Reject missing configuration only for the selected recognizer."""
        match model:
            case ModelName.PADDLE:
                fields = tuple(
                    field
                    for field, value in (
                        ("PADDLE_ENDPOINT", self.paddle_endpoint),
                        ("PADDLE_MODEL", self.paddle_model),
                    )
                    if not value
                )
            case ModelName.GPT:
                fields = ("CODEX_MODEL",) if not self.codex_model else ()
            case ModelName.GEMINI:
                fields = ("AGY_MODEL",) if not self.agy_model else ()
        if fields:
            raise MissingModelConfigurationError(model=model, fields=fields)
