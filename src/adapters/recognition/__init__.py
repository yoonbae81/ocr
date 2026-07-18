"""Recognition adapter selection."""

from application.ports.recognizer import RecognizerPort
from settings import ModelName, Settings

from .agy import AgyAdapter
from .codex import CodexAdapter
from .errors import UnsupportedEffortError, UnsupportedModelError
from .paddle import PaddleAdapter


def recognizer_for(model: str, *, settings: Settings, effort: str) -> RecognizerPort:
    """Build the recognition adapter selected by the CLI model option."""
    match model:
        case "gpt":
            settings.validate_for_model(ModelName.GPT)
            return CodexAdapter(
                model=settings.codex_model,
                effort=effort,
                timeout=settings.recognition_timeout,
            )
        case "gemini" if effort == "low":
            settings.validate_for_model(ModelName.GEMINI)
            return AgyAdapter(
                model=settings.agy_model,
                timeout=settings.recognition_timeout,
            )
        case "paddle" if effort == "low":
            settings.validate_for_model(ModelName.PADDLE)
            return PaddleAdapter(
                endpoint=settings.paddle_endpoint,
                model=settings.paddle_model,
            )
        case "gemini" | "paddle":
            raise UnsupportedEffortError(model=model, effort=effort)
        case unsupported:
            raise UnsupportedModelError(model=unsupported)


__all__ = ["AgyAdapter", "CodexAdapter", "PaddleAdapter", "recognizer_for"]
