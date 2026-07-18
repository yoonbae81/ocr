from threading import Barrier

from adapters.recognition.errors import RecognitionError
from application.transcribe import transcribe_pages
from domain.content import ImagePage, PageNumber, SourceKind


class BarrierRecognizer:
    def __init__(self, expected_calls: int) -> None:
        self._barrier: Barrier = Barrier(expected_calls, timeout=2.0)

    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        _ = self._barrier.wait()
        return f"recognized {page.page}"


def test_transcribe_pages_when_concurrency_is_three_runs_requests_in_parallel() -> None:
    # Given: three image pages and a recognizer requiring three simultaneous calls.
    pages = tuple(
        ImagePage(
            page=PageNumber(page_number),
            image=b"png",
            media_type="image/png",
            source=SourceKind.IMAGE,
        )
        for page_number in range(1, 4)
    )
    recognizer = BarrierRecognizer(expected_calls=3)

    # When: pages are transcribed with three workers.
    content, failures = transcribe_pages(pages, recognizer, "prompt", concurrency=3)

    # Then: all requests complete and output remains in source page order.
    assert [page.body for page in content] == [
        "recognized 1",
        "recognized 2",
        "recognized 3",
    ]
    assert failures == []


class FailingRecognizer:
    def recognize(self, page: ImagePage, prompt: str) -> str:
        _ = prompt
        if page.page == 2:
            raise RecognitionError(detail="unavailable")
        return f"recognized {page.page}"


def test_transcribe_pages_when_one_request_fails_retains_other_pages() -> None:
    # Given: three pages and a recognizer that cannot process the middle page.
    pages = tuple(
        ImagePage(
            page=PageNumber(page_number),
            image=b"png",
            media_type="image/png",
            source=SourceKind.IMAGE,
        )
        for page_number in range(1, 4)
    )

    # When: the batch is transcribed through the application concurrency boundary.
    content, failures = transcribe_pages(
        pages,
        FailingRecognizer(),
        "prompt",
        concurrency=2,
    )

    # Then: successful pages and the isolated failure remain source ordered.
    assert [page.page for page in content] == [PageNumber(1), PageNumber(3)]
    assert [(failure.page, failure.reason) for failure in failures] == [
        (PageNumber(2), "unavailable")
    ]
