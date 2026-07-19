from functools import lru_cache
from pathlib import Path
from typing import Annotated, Final

import fitz
import typer

from adapters.output.markdown import MarkdownOutput
from adapters.recognition import recognizer_for
from adapters.source.image import ImageSource
from adapters.source.pdf import PdfSource
from adapters.source.zip import ZipSource
from application.checkpoint import merge_status
from application.observability import get_logger
from application.pages import acquire_pages
from application.ports.recognizer import RecognizerPort
from application.ports.source import PageSourcePort
from application.status import pending_pages
from application.transcribe import transcribe_pages
from domain.content import PageContent, PageNumber
from domain.document import Document
from domain.status import PageFailure
from settings import MissingPaddleConfigurationError, Settings

app = typer.Typer()
PAGE_RANGE_PARTS: Final = 2
_INVALID_PAGE_RANGE: Final = (
    "must be a positive page number or ascending range such as 5-15"
)
_IMAGE_PAGE_ONLY: Final = "image inputs only support page 1"


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings.model_validate({})


@app.command()
def ocr(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=False,
        ),
    ],
    page_or_range: Annotated[str, typer.Argument()],
    retry_failed: Annotated[bool, typer.Option("--retry-failed")] = False,
    retry_attempts: Annotated[int, typer.Option("--retry-attempts")] = 1,
) -> None:
    """Transcribe selected local PDF, image, or ZIP pages into canonical Markdown."""
    logger = get_logger()
    document = Document(input_file)
    pages = _selected_pages(page_or_range)
    source = _source_for(document)
    _validate_selection(document, pages)
    output = MarkdownOutput(Path.cwd() / document.name)
    document_id = document.path.resolve().as_posix()
    previous_status = output.load_status(document=document_id)
    pending = pending_pages(pages, previous_status, retry_failed=retry_failed)
    if not pending:
        logger.info("ocr.skipped", reason="already_completed")
        return
    settings = _settings()
    recognizer = _recognizer()
    logger.info(
        "ocr.started",
        model="paddle",
        page_count=len(pending),
        concurrency=settings.concurrency,
        retry_attempts=retry_attempts,
    )
    acquired = acquire_pages(source, document, pending)
    status = previous_status

    def _on_page_completed(outcome: PageContent | PageFailure) -> None:
        nonlocal status
        content_batch: tuple[PageContent, ...] = (
            (outcome,) if isinstance(outcome, PageContent) else ()
        )
        failure_batch: tuple[PageFailure, ...] = (
            (outcome,) if isinstance(outcome, PageFailure) else ()
        )
        status = merge_status(
            status,
            content_batch,
            failure_batch,
            document=document_id,
        )
        _ = output.write(content_batch, status, source_name=document.path.name)

    content, failures = transcribe_pages(
        acquired,
        recognizer,
        "",
        settings.concurrency,
        max_retries=retry_attempts,
        on_page_completed=_on_page_completed,
    )
    status = merge_status(status, tuple(content), tuple(failures), document=document_id)
    _ = output.write(tuple(content), status, source_name=document.path.name)
    logger.info(
        "ocr.batch_completed", completed_count=len(content), failure_count=len(failures)
    )
    if failures:
        logger.warning("ocr.completed", failure_count=len(failures))
        raise typer.Exit(code=1)
    logger.info("ocr.completed", failure_count=0)


def _selected_pages(raw: str) -> tuple[PageNumber, ...]:
    parts = raw.split("-")
    if len(parts) == 1 and parts[0].isdecimal():
        page = PageNumber(int(parts[0]))
        if page > 0:
            return (page,)
    if len(parts) == PAGE_RANGE_PARTS and all(part.isdecimal() for part in parts):
        start, end = (PageNumber(int(part)) for part in parts)
        if start > 0 and start <= end:
            return tuple(PageNumber(page) for page in range(start, end + 1))
    raise typer.BadParameter(_INVALID_PAGE_RANGE, param_hint="page_or_range")


def _source_for(document: Document) -> PageSourcePort:
    match document.path.suffix.lower():
        case ".pdf":
            return PdfSource()
        case ".jpg" | ".jpeg" | ".png":
            return ImageSource()
        case ".zip":
            return ZipSource()
        case _:
            message = f"unsupported input document: {document.path}"
            raise typer.BadParameter(message, param_hint="input_file")


def _validate_selection(document: Document, pages: tuple[PageNumber, ...]) -> None:
    match document.path.suffix.lower():
        case ".pdf":
            with fitz.open(document.path) as pdf:
                if pages[-1] > pdf.page_count:
                    message = f"page {pages[-1]} is not available"
                    raise typer.BadParameter(message, param_hint="page_or_range")
        case ".jpg" | ".jpeg" | ".png":
            if pages != (PageNumber(1),):
                raise typer.BadParameter(_IMAGE_PAGE_ONLY, param_hint="page_or_range")
        case ".zip":
            available_pages = ZipSource().available_pages(document.path)
            unavailable = next(
                (page for page in pages if page not in available_pages), None
            )
            if unavailable is not None:
                message = f"page {unavailable} is not available"
                raise typer.BadParameter(message, param_hint="page_or_range")
        case _:
            message = f"unsupported input document: {document.path}"
            raise typer.BadParameter(message, param_hint="input_file")


def _recognizer() -> RecognizerPort:
    try:
        return recognizer_for(settings=_settings())
    except MissingPaddleConfigurationError as error:
        raise typer.BadParameter(str(error)) from None
