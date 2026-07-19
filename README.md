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

입력 파일을 작업 디렉터리에 직접 두고 실행합니다.

```bash
mkdir -p workspace
cp /path/to/book.pdf workspace/book.pdf
cd workspace
uv run --project .. ocr book.pdf 1-3
```

## 지원 범위

- 입력: `.pdf`, `.jpg`, `.jpeg`, `.png`, 이미지가 든 `.zip`
- 페이지 선택: 양의 정수(`5`) 또는 오름차순 범위(`5-15`)
- 출력: 원본 물리 페이지마다 Markdown 파일 하나
- 인식 백엔드: PaddleOCR-VL
- 완료/실패 상태 저장과 실패 페이지만 재시도

단일 이미지는 논리적 1페이지만 지원합니다. ZIP 안의 이미지 파일은 파일명 끝의 숫자를
페이지 번호로 사용합니다. 예를 들어 `page-001.png`은 1페이지입니다.

## 사용법

```bash
cd workspace
uv run --project .. ocr INPUT_FILE PAGE_OR_RANGE [OPTIONS]
```

```bash
# 5~15페이지를 PaddleOCR-VL로 인식
uv run --project .. ocr book.pdf 5-15

# 단일 이미지 입력
uv run --project .. ocr scan.png 1
```

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `--retry-failed` | 기록된 실패 페이지만 다시 처리 | 꺼짐 |

한 페이지 이상이 실패하면 실패 내용을 저장한 뒤 종료 코드 `1`로 끝납니다.

## 출력과 재개

```text
workspace/
├─ book.pdf
└─ book/
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

PaddleOCR-VL 서비스에 접근할 수 있어야 하며, `.env`에 엔드포인트와 모델을 설정합니다.

```dotenv
PADDLE_ENDPOINT=http://localhost:8111/
PADDLE_MODEL=matrixmaven/PaddleOCR-VL-1.6-MLX
CONCURRENCY=1
RECOGNITION_TIMEOUT=300
```


## 마이그레이션

`--group`과 `--toc-offset`은 제거되었습니다. 결과는 항상
`<입력 파일명(확장자 제외)>/<page>.md`이며,
구조화와 참고자료 매칭은 이 저장소 밖의 후속 단계에서 수행해야 합니다.

## 개발 및 검증

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```
