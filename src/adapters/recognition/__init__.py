"""Recognition adapter selection."""

from application.ports.recognizer import RecognizerPort
from settings import Settings

from .paddle import PaddleAdapter


def recognizer_for(*, settings: Settings) -> RecognizerPort:
    """Build the project's PaddleOCR recognizer."""
    settings.validate_paddle_configuration()
    return PaddleAdapter(
        endpoint=settings.paddle_endpoint,
        model=settings.paddle_model,
    )


__all__ = ["PaddleAdapter", "recognizer_for"]
