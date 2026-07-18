"""Document page source adapters."""

from adapters.source.image import ImageSource
from adapters.source.pdf import PdfSource
from adapters.source.zip import ZipSource

__all__ = ["ImageSource", "PdfSource", "ZipSource"]
