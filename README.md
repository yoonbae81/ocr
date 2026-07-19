# OCR

로컬 PDF, 단일 이미지, 이미지 ZIP에서 선택한 물리 페이지를 OCR하여 페이지별 Markdown
정본으로 저장하는 Python CLI입니다. 이 도구는 원본 페이지 OCR과 처리 상태만 관리합니다.
문서 구조화나 참고자료 매칭은 별도 단계의 책임입니다.

## 빠른 시작

Python 3.13 이상과 [uv](https://docs.astral.sh/uv)가 필요합니다.

```bash
git clone <repository-url>
cd ocr
uv sync --dev
cp .env.example .env
```

문서별 작업 디렉터리에서 실행합니다.

```bash
mkdir -p workspace/book
cp /path/to/book.pdf workspace/book/book.pdf
cd workspace/book
uv run --project ../.. ocr book.pdf 1-3 --model gpt
```

## 지원 범위

- 입력: `.pdf`, `.jpg`, `.jpeg`, `.png`, 이미지가 든 `.zip`
- 페이지 선택: 양의 정수(`5`) 또는 오름차순 범위(`5-15`)
- 출력: 원본 물리 페이지마다 Markdown 파일 하나
- 인식 백엔드: `gpt`, `gemini`, `paddle`
- 완료/실패 상태 저장과 실패 페이지만 재시도
- 작업 디렉터리별 OCR 지침(`prompt.md`)

단일 이미지는 논리적 1페이지만 지원합니다. ZIP 안의 이미지 파일은 파일명 끝의 숫자를
페이지 번호로 사용합니다. 예를 들어 `page-001.png`은 1페이지입니다.

## 사용법

```bash
cd workspace/book
uv run --project ../.. ocr INPUT_FILE PAGE_OR_RANGE [OPTIONS]
```

```bash
# 5페이지만 PaddleOCR-VL로 인식
uv run --project ../.. ocr book.pdf 5 --model paddle

# 5~15페이지를 GPT로 인식
uv run --project ../.. ocr book.pdf 5-15 --model gpt --effort low

# 단일 이미지 입력
uv run --project ../.. ocr scan.png 1 --model gemini
```

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--model` | `gpt`, `gemini`, `paddle` 중 인식 방식 | `DEFAULT_MODEL` |
| `--effort` | 인식 노력 수준 | `low` |
| `--retry-failed` | 기록된 실패 페이지만 다시 처리 | 꺼짐 |

한 페이지 이상이 실패하면 실패 내용을 저장한 뒤 종료 코드 `1`로 끝납니다.

## 출력과 재개

```text
workspace/book/
├─ book.pdf
├─ prompt.md                         # 선택: OCR 전사 지시
└─ output/
   ├─ 0001.md
   ├─ 0002.md
   ├─ 0055.md
   └─ status.md
```

모든 성공 페이지는 원본 물리 페이지 번호를 최소 네 자리로 0 채워 저장합니다. 10,000쪽
이상은 자릿수를 늘려 그대로 저장하므로 충돌하지 않습니다. 각 파일에는 입력 파일명과
페이지 번호를 가진 YAML front matter가 있고, 본문은 해당 페이지 OCR 결과만 담습니다.

```markdown
---
source: "book.pdf"
page: 55
---

OCR 본문
```

`status.md`는 입력 문서 식별자, 완료 페이지, 실패 페이지와 원인을 기록합니다. 같은 입력
문서를 다시 실행하면 완료 페이지는 건너뛰며, `--retry-failed`는 실패한 페이지만 다시
OCR합니다. 다른 입력 문서를 같은 작업 디렉터리에서 실행하면 이전 상태를 재개에 쓰지
않습니다.

## 인식 방식과 설정

`.env`에서 사용할 인식 방식을 설정합니다.

| 방식 | 필요한 환경 | 필수 설정 | 비고 |
| --- | --- | --- | --- |
| `gpt` | 로그인된 `codex` CLI | `CODEX_MODEL` | `--effort` 사용 가능 |
| `gemini` | 로그인된 `agy` CLI | `AGY_MODEL` | `--effort low`만 지원 |
| `paddle` | 접근 가능한 PaddleOCR-VL 서비스 | `PADDLE_ENDPOINT`, `PADDLE_MODEL` | `--effort low`만 지원 |

```dotenv
PADDLE_ENDPOINT=http://localhost:8111/
PADDLE_MODEL=matrixmaven/PaddleOCR-VL-1.6-MLX
CODEX_MODEL=gpt-5.6-luna
AGY_MODEL=gemini-3.5-flash
DEFAULT_MODEL=gpt
CONCURRENCY=1
RECOGNITION_TIMEOUT=300
```

`prompt.md`를 작업 디렉터리 또는 상위 작업 디렉터리에 두면 GPT와 Gemini의 추가 전사
지시로 사용합니다. PaddleOCR-VL은 추가 프롬프트를 사용하지 않습니다.

## 마이그레이션

`--group`과 `--toc-offset`은 제거되었습니다. 결과는 항상 `output/<page>.md`이며,
구조화와 참고자료 매칭은 이 저장소 밖의 후속 단계에서 수행해야 합니다.

## 개발 및 검증

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```
