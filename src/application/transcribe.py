"""Page transcription use case."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        case TextPage(page=number, text=text):
            return PageContent(page=number, body=text)
        case ImagePage(page=number):
            return PageContent(page=number, body=recognizer.recognize(page, prompt))


def transcribe_pages(
    pages: tuple[SourcePage, ...],
    recognizer: RecognizerPort,
    prompt: str,
    concurrency: int = 1,
    max_retries: int = 1,
    on_page_completed: Callable[[PageContent | PageFailure], None] | None = None,
) -> tuple[list[PageContent], list[PageFailure]]:
    """Convert pages concurrently while retaining page-level failures."""
    attempts = max(1, max_retries + 1)
    if concurrency == 1:
        outcomes = []
        for page in pages:
            outcome = _transcribe_outcome(
                page, recognizer, prompt, max_attempts=attempts
            )
            if on_page_completed is not None:
                on_page_completed(outcome)
            outcomes.append(outcome)
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(pages))) as executor:
            futures = {
                executor.submit(
                    _transcribe_outcome,
                    page,
                    recognizer,
                    prompt,
                    max_attempts=attempts,
                ): page
                for page in pages
            }
            outcomes_by_page: dict[int, PageContent | PageFailure] = {}
            for future in as_completed(futures):
                outcome = future.result()
                if on_page_completed is not None:
                    on_page_completed(outcome)
                outcomes_by_page[futures[future].page] = outcome
            outcomes = tuple(
                outcomes_by_page[page.page]
                for page in pages
                if page.page in outcomes_by_page
            )

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
    max_attempts: int = 1,
) -> PageContent | PageFailure:
    last_error: Exception | None = None
    for _ in range(1, max_attempts + 1):
        try:
            return transcribe_page(page, recognizer, prompt)
        except RecognitionError as error:
            last_error = error
    if last_error is None:
        last_error = Exception("unknown recognition error")
    return PageFailure(page=page.page, reason=str(last_error))
