# OCR

로컬 PDF, 이미지, 이미지 ZIP의 원하는 페이지만 인식해 Markdown으로 저장하는 Python
CLI입니다. GPT(Codex CLI), Gemini(Agy CLI), PaddleOCR-VL 중 하나를 선택할 수 있고,
페이지·장·책 단위로 결과를 묶습니다. 실행 상태를 기록하므로 같은 문서를 이어서
처리하거나 실패한 페이지만 다시 시도할 수 있습니다.

## 빠른 시작

요구 사항은 Python 3.13 이상과 [uv](https://docs.astral.sh/uv/)입니다. 저장소를
clone한 뒤 프로젝트 루트에서 의존성과 환경 파일을 준비합니다.

```bash
git clone <repository-url>
cd ocr
uv sync --dev
cp .env.example .env
```

`.env`에서 사용할 인식 방식의 설정을 확인한 후, 문서별 작업 디렉터리에서 실행합니다.

```bash
mkdir -p workspace/book
cp /path/to/book.pdf workspace/book/book.pdf
cd workspace/book
uv run --project ../.. ocr book.pdf 1-3 --model gpt --group page
```

결과는 `workspace/book/output/`에 생성됩니다. `.env`와 `workspace/`는
기본적으로 Git에서 제외됩니다.

## 지원 범위

- 입력: `.pdf`, `.jpg`, `.jpeg`, `.png`, 이미지가 든 `.zip`
- 페이지 선택: 양의 정수(`5`) 또는 오름차순 범위(`5-15`)
- 출력 묶음: 페이지별(`page`), 목차 기반 장별(`chapter`), 책 전체(`book`)
- 인식 백엔드: `gpt`, `gemini`, `paddle`
- 상태 저장, 실패 기록, 실패 페이지만 재시도
- 작업 디렉터리별 추가 지침(`prompt.md`)

이미지 단일 파일은 논리적 1페이지만 지원합니다. ZIP 안의 이미지 파일은 이름 끝의
숫자를 페이지 번호로 사용합니다. 예를 들어 `page-001.png`은 1페이지입니다.

## 인식 방식과 설정

선택한 방식에 필요한 실행 환경을 먼저 준비하세요.

| 방식 | 필요한 환경 | 필수 설정 | 비고 |
| --- | --- | --- | --- |
| `gpt` | 로그인된 `codex` CLI | `CODEX_MODEL` | `--effort` 사용 가능 |
| `gemini` | 로그인된 `agy` CLI | `AGY_MODEL` | `--effort low`만 지원 |
| `paddle` | 접근 가능한 PaddleOCR-VL 서비스 | `PADDLE_ENDPOINT`, `PADDLE_MODEL` | `--effort low`만 지원, 추가 프롬프트 미지원 |

`.env`는 저장소 루트에 둡니다. CLI를 `workspace/` 아래에서 실행해도 이 파일을
읽습니다. 필요한 값은 `.env.example`에서 시작하세요.

```dotenv
# 선택한 방식에 해당하는 값은 반드시 설정합니다.
PADDLE_ENDPOINT=http://localhost:8111/
PADDLE_MODEL=matrixmaven/PaddleOCR-VL-1.6-MLX
CODEX_MODEL=gpt-5.6-luna
AGY_MODEL=gemini-3.5-flash

# 공통 설정
DEFAULT_MODEL=gpt
CONCURRENCY=1
RECOGNITION_TIMEOUT=300
```

- `DEFAULT_MODEL`: `--model`을 생략했을 때의 방식입니다. `gpt`, `gemini`, `paddle`
  중 하나여야 합니다.
- `CONCURRENCY`: 페이지 인식 동시 작업 수이며 기본값은 `1`입니다.
- `RECOGNITION_TIMEOUT`: Codex CLI와 Agy CLI의 페이지당 제한 시간(초)이며 기본값은
  `300`입니다.

선택한 어댑터가 외부 서비스를 사용하도록 구성되어 있다면 문서 페이지와
`prompt.md` 내용이 그 서비스에 전달될 수 있습니다. 민감한 자료는 실행 전에 해당
서비스의 보안·보존 정책을 확인하세요.

## 작업 디렉터리

문서 한 권(또는 한 묶음)을 하나의 작업 디렉터리로 관리하는 방식을 권장합니다.

```text
workspace/
└── book/
    ├── book.pdf              # 또는 이미지 파일/이미지 ZIP
    ├── toc.md                # 선택 사항: chapter 그룹용 목차
    ├── prompt.md             # 선택 사항: 인식 추가 지침
    └── output/               # 생성됨: Markdown과 status.md
```

## 사용법

```bash
cd workspace/book
uv run --project ../.. ocr INPUT_FILE PAGE_OR_RANGE [OPTIONS]
```

```bash
# 5페이지만 PaddleOCR-VL로 인식
uv run --project ../.. ocr book.pdf 5 --model paddle --group page

# 5~15페이지를 GPT로 장별 저장
uv run --project ../.. ocr book.pdf 5-15 --model gpt --effort low --group chapter

# 단일 이미지 입력
uv run --project ../.. ocr scan.png 1 --model gemini --group page
```

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--model` | `gpt`, `gemini`, `paddle` 중 인식 방식 | `DEFAULT_MODEL` |
| `--effort` | 인식 노력 수준 | `low` |
| `--group` | `page`, `chapter`, `book` 중 출력 묶음 방식 | 아래 참고 |
| `--toc-offset` | 인쇄 목차 페이지를 입력 페이지로 보정할 값 | `0` |
| `--retry-failed` | 기록된 실패 페이지만 다시 처리 | 꺼짐 |

`--group`을 생략하면 현재 작업 디렉터리에 `toc.md`가 있을 때는 `chapter`, 없을
때는 `page`를 사용합니다. `chapter`는 유효한 장 항목이 있는 `toc.md`가 필요하며,
`page`와 `book`은 목차 없이 사용할 수 있습니다.

명령 진행 상황은 표준 오류로 JSON 로그(`ocr.started`, `ocr.batch_completed`,
`ocr.completed`)를 출력합니다. 페이지 하나 이상이 실패하면 실패 내용을 저장한 뒤
종료 코드 `1`로 끝납니다.

## 목차 기반 장별 저장

`--group chapter`에서는 `toc.md`의 장 시작 페이지를 이용해 결과를 나눕니다. 목차의
페이지 번호는 입력 파일의 물리적 페이지가 아니라 책에 인쇄된 페이지 번호로 씁니다.
둘의 차이는 `--toc-offset`으로 보정합니다.

```markdown
# Table of Contents

## Part One | page: 1

### Foundations | page: 12

### Practice | page: 35

## Part Two | page: 51

### Applications | page: 60
```

상위 파트가 없다면 `## Contents` 아래에 `### 장 제목 | page: N` 형식으로 작성할 수
있습니다. 페이지 번호는 양의 정수이고 오름차순이어야 합니다.

```bash
# PDF 앞에 표지가 3페이지 있어 인쇄 1쪽이 입력 4쪽인 경우
uv run --project ../.. ocr book.pdf 1-120 --group chapter --toc-offset 3
```

## 추가 프롬프트

GPT와 Gemini는 기본 전사 지시를 사용합니다. `workspace/prompt.md`를 두면 모든 책에
공통으로 적용하며, `workspace/book/prompt.md`를 두면 책별 지시로 이를 덮어씁니다.
PaddleOCR-VL은 자유 형식 추가 프롬프트를 지원하지 않으므로, `prompt.md`가 있으면
무시했다는 JSON 경고를 출력하고 OCR을 계속합니다.

```markdown
원문의 언어와 문단 구조를 유지해 Markdown으로 변환해.
표와 수식은 가능한 한 원래 구조를 보존해.
```

## 출력과 재개

권장 작업 구조에서는 모든 결과가 `workspace/book/output/`에 저장됩니다.

```text
workspace/book/output/
├── 5.md                    # page 그룹
├── Foundations.md          # chapter 그룹
├── Part One/
│   └── Foundations.md      # 파트가 있는 chapter 그룹
├── book.md                 # book 그룹
└── status.md               # 문서 식별자와 처리 상태
```

각 페이지에는 `<!-- page: N -->` 주석이 들어갑니다. 장과 책 결과는 기존 페이지 블록을
보존하며 새로 인식한 페이지를 병합합니다. 출력 파일명에 사용할 수 없는 문자는 제거되고,
빈 제목은 `untitled`로 저장됩니다.

`status.md`에는 다음이 기록됩니다.

- `Document`: 상태가 속한 입력 문서의 절대 경로
- `Completed`: 정상 처리한 페이지
- `Failed`: 페이지 번호와 실패 원인
- `Current Chapter`: 마지막으로 저장한 장

같은 입력 문서와 범위를 다시 실행하면 완료 페이지는 건너뜁니다. 기본 실행에서는
이전에 실패한 페이지도 건너뛰므로, 실패 페이지만 다시 시도할 때는 다음처럼 실행하세요.

```bash
uv run --project ../.. ocr book.pdf 1-120 --group chapter --retry-failed
```

다른 입력 문서를 같은 작업 디렉터리에서 실행하면 이전 상태는 재개에 사용하지 않습니다.
이전 결과 파일까지 분리하려면 문서마다 별도 작업 디렉터리를 사용하세요.

## 개발 및 검증

```bash
uv sync --dev
uv run pytest
uv run pytest --cov-report=html
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv build
```

CLI의 전체 옵션은 다음으로 확인할 수 있습니다.

```bash
uv run ocr --help
```
