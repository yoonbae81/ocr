"""Recognition adapters backed by OCR engines."""

from .mlx import MlxPaddleRecognizerAdapter
from .openvino import OpenVinoPaddleRecognizerAdapter

__all__ = ["MlxPaddleRecognizerAdapter", "OpenVinoPaddleRecognizerAdapter"]
