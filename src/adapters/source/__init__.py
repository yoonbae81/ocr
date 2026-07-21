"""Source adapters for supported input types."""

from .image import ImageSourceAdapter
from .pdf import PdfSourceAdapter
from .zip import ZipSourceAdapter

__all__ = ["ImageSourceAdapter", "PdfSourceAdapter", "ZipSourceAdapter"]
