"""Page transcription use case."""

from concurrent.futures import ThreadPoolExecutor

from adapters.recognition.errors import RecognitionError
from application.ports.recognizer import RecognizerPort
from domain.content import ImagePage, PageContent, SourcePage, TextPage
from domain.status import PageFailure


def transcribe_page(
    page: SourcePage,
    recognizer: RecognizerPort,
    prompt: str,
) -> PageContent:
    """Convert one source page into format-neutral page content."""
    match page:
        case TextPage(page=number, text=text, chapter=chapter, source=source):
            return PageContent(
                page=number,
                body=text,
                chapter=chapter,
                source=source,
            )
        case ImagePage(page=number, chapter=chapter, source=source):
            return PageContent(
                page=number,
                body=recognizer.recognize(page, prompt),
                chapter=chapter,
                source=source,
            )


def transcribe_pages(
    pages: tuple[SourcePage, ...],
    recognizer: RecognizerPort,
    prompt: str,
    concurrency: int = 1,
) -> tuple[list[PageContent], list[PageFailure]]:
    """Convert pages concurrently while retaining page-level failures."""
    if concurrency == 1:
        outcomes = tuple(
            _transcribe_outcome(page, recognizer, prompt) for page in pages
        )
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(pages))) as executor:
            futures = tuple(
                executor.submit(_transcribe_outcome, page, recognizer, prompt)
                for page in pages
            )
            outcomes = tuple(future.result() for future in futures)

    content: list[PageContent] = []
    failures: list[PageFailure] = []
    for outcome in outcomes:
        match outcome:
            case PageContent():
                content.append(outcome)
            case PageFailure():
                failures.append(outcome)
    return content, failures


def _transcribe_outcome(
    page: SourcePage,
    recognizer: RecognizerPort,
    prompt: str,
) -> PageContent | PageFailure:
    try:
        return transcribe_page(page, recognizer, prompt)
    except RecognitionError as error:
        return PageFailure(page=page.page, reason=str(error))
