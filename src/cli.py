from functools import lru_cache
from pathlib import Path
from typing import Annotated, Final

import fitz
import typer

from adapters.output.markdown import MarkdownOutput
from adapters.recognition import recognizer_for
from adapters.recognition.errors import UnsupportedEffortError, UnsupportedModelError
from adapters.source.image import ImageSource
from adapters.source.pdf import PdfSource
from adapters.source.zip import ZipSource
from application.checkpoint import merge_status
from application.observability import get_logger
from application.pages import acquire_pages
from application.ports.recognizer import RecognizerPort
from application.ports.source import PageSourcePort
from application.prompt import DEFAULT_TRANSCRIPTION_PROMPT, workspace_prompt_path
from application.status import pending_pages
from application.transcribe import transcribe_pages
from domain.content import PageContent, PageNumber, SourcePage
from domain.document import Document
from domain.status import PageFailure
from settings import MissingModelConfigurationError, ModelName, Settings

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
    model: Annotated[
        ModelName, typer.Option(default_factory=lambda: _settings().default_model)
    ],
    effort: Annotated[str, typer.Option()] = "low",
    retry_failed: Annotated[bool, typer.Option("--retry-failed")] = False,
) -> None:
    """Transcribe selected local PDF, image, or ZIP pages into canonical Markdown."""
    logger = get_logger()
    document = Document(input_file)
    pages = _selected_pages(page_or_range)
    source = _source_for(document)
    _validate_selection(document, pages)
    output = MarkdownOutput(Path.cwd() / "output")
    document_id = document.path.resolve().as_posix()
    previous_status = output.load_status(document=document_id)
    pending = pending_pages(pages, previous_status, retry_failed=retry_failed)
    if not pending:
        logger.info("ocr.skipped", reason="already_completed")
        return
    settings = _settings()
    recognizer = _recognizer(model, effort)
    prompt_path = workspace_prompt_path(Path.cwd())
    prompt = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path is not None
        else DEFAULT_TRANSCRIPTION_PROMPT
    )
    if model is ModelName.PADDLE:
        if prompt_path is not None:
            logger.warning("ocr.prompt_ignored", model=model.value)
        prompt = ""
    logger.info(
        "ocr.started",
        model=model.value,
        page_count=len(pending),
        concurrency=settings.concurrency,
    )
    acquired = acquire_pages(source, document, pending)
    content, failures = _transcribe_acquired(
        acquired, recognizer=recognizer, prompt=prompt, concurrency=settings.concurrency
    )
    status = merge_status(
        previous_status, tuple(content), tuple(failures), document=document_id
    )
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


def _recognizer(model: ModelName, effort: str) -> RecognizerPort:
    try:
        return recognizer_for(model.value, settings=_settings(), effort=effort)
    except MissingModelConfigurationError as error:
        raise typer.BadParameter(str(error), param_hint="model") from None
    except UnsupportedEffortError as error:
        raise typer.BadParameter(str(error), param_hint="effort") from None
    except UnsupportedModelError as error:
        raise typer.BadParameter(str(error), param_hint="model") from None


def _transcribe_acquired(
    acquired: tuple[SourcePage, ...],
    *,
    recognizer: RecognizerPort,
    prompt: str,
    concurrency: int,
) -> tuple[list[PageContent], list[PageFailure]]:
    """Recognize already-acquired pages and retain page-level failures."""
    return transcribe_pages(acquired, recognizer, prompt, concurrency)
