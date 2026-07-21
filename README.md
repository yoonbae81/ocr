# Local OCR

## 설치 / 사용법

요구사항: Apple Silicon macOS, `uv`

```zsh
git clone <repository-url> ocr
cd ocr
make install
```

`make install`은 `uv sync --all-groups`로 의존성을 맞추고, 프로젝트를 editable 모드로 등록한 뒤 현재 셸에서 `ocr` 실행 경로를 등록합니다.

설치 후:

```zsh
ocr --help
ocr /path/to/book.pdf 1-3
ocr /path/to/scan.jpg 1
ocr "*.pdf" 1-3
```

개발 중에는 `make sync`, `make test`, `make lint`, `make typecheck`, `make check`를 사용할 수 있습니다.

`uv`를 쓰지 않거나 전역 설치를 원하지 않을 때는 아래처럼 바로 실행할 수 있습니다.

```zsh
uv run ocr /path/to/book.pdf 1-3
```

## 기본 동작

- 입력: PDF/이미지/ZIP
- 출력: 현재는 **Markdown**만 지원
- 출력 대상 폴더: 실행 디렉터리에 입력 파일명과 동일한 폴더를 만들고 페이지별로 `1.md`, `2.md` ... 저장
- 이미지: `img/` 하위에 본문에서 추출된 이미지 영역만 저장
  - 파일명 규칙: `<page>_<start_x>_<start_y>_<end_x>_<end_y>.jpg`

예시:

```text
./book/
├── 1.md
├── 2.md
└── img/
    └── 2_369_1899_1903_2660.jpg
```

`ocr`는 페이지 번호가 1부터 시작하는 “물리 페이지” 기준으로 인식합니다.

## CLI 사용 예

```zsh
# 1~3쪽만 처리
ocr /path/to/book.pdf 1-3

# 현재 폴더의 PDF를 순차 처리
ocr "*.pdf" 1-3

# 페이지 점프(1,5~8)
ocr /path/to/book.pdf 1,5-8

# 출력 덮어쓰기
ocr /path/to/book.pdf 1-3 --replace

# 이미 생성된 파일 건너뛰기(재시작)
ocr /path/to/book.pdf 1-3 --resume

# 배치/캐시/성능 제어
ocr /path/to/book.pdf 1-3 --batch-size 8 --cache-dir ~/.cache/ocr/raw
ocr /path/to/book.pdf 1-3 --no-cache
ocr /path/to/book.pdf 1-3 --server-url http://127.0.0.1:9010 --vl-concurrency 4
ocr /path/to/book.pdf 1-3 --profile
```

명령 형식: `ocr <파일/패턴> <페이지>`

옵션 요약:

- `pages`(필수 위치 인자): `1,5-8` 형식 지정
- `--dpi`: PDF 렌더링 해상도 (기본값 300)
- `--zip-prefix`: ZIP 내부 파일명 충돌 방지용 프리픽스
- `--replace`: 기존 페이지 덮어쓰기
- `--resume`: 이미 존재하는 페이지 스킵
- `--batch-size`: Paddle 페이지 배치 크기(기본 4)
- `--cache/--no-cache`: OCR 원문 캐시 사용 여부(기본 사용)
- `--cache-dir`: 캐시 경로 지정
- `--server-url`: 이미 실행 중인 MLX 서버에 연결
- `--vl-concurrency`: VL 요청 동시성 상한
- `--profile`: 준비/캐시/인식/전체 시간 출력

## 아키텍처(헥사고날)

현재 구조:

- `cli.py`: `typer` CLI 진입점
- `application.py`: 페이지 선택·캐시 사용·인식 결과 기록 플로우
- `adapters/recognition/paddle.py`: PaddleOCR-VL 호출 어댑터
- `mlx_server.py`: 로컬 MLX 서버 생명주기 관리
- `ports/source.py`: 입력 소스 포트(계약)
- `adapters/source/{image.py,pdf.py,zip.py}`: PDF/JPG/PNG/WEBP/ZIP 입력 구현
- `ports/cache.py`, `ports/output.py`: 포트(인터페이스)
- `adapters/cache/*`: 캐시 어댑터 (`filesystem`, `disabled`)
- `adapters/output/*`: 출력 어댑터(`markdown`)

핵심 포인트:

- 캐시는 렌더된 페이지 이미지 바이트 + 모델 이름으로 키를 만들어 저장됩니다.
- 캐시 히트가 있으면 해당 페이지는 재인식을 하지 않아도 됩니다.
- 캐시 미스가 있고 `--server-url`이 없으면 현재 프로세스가 MLX 서버를 자동으로 띄우고 완료 후 종료합니다.
- `--resume`은 기존 Markdown 파일이 이미 있으면 OCR 단계 자체를 건너뜁니다.

## Postprocess(후처리) 구조

`markdown` 출력은 `MarkdownPageExporter`가 페이지 저장 전에 후처리를 수행합니다.

현재 규칙 저장 위치:

- `src/adapters/output/rules/markdown/base.txt`
- `src/adapters/output/rules/markdown/img.txt`

`base.txt`는 공통 텍스트 정리 규칙(예: \\underline 텍스트 정리)이고,
`img.txt`는 이미지 정렬/표기 정리 규칙 같은 도메인 특화 규칙을 분리해 둔 형태입니다.

규칙은 `src/adapters/output/markdown_postprocessor.py`에서 로드되어 Markdown 최종 텍스트에 적용됩니다.

포맷이 늘어나면(`epub` 등) `src/adapters/output/rules/epub/*.txt`처럼 포맷 단위로 규칙을 추가하면 됩니다.

## 참고

- 기본 설치/실행 경로가 바뀌지 않도록 `make install`/`make uninstall`을 권장합니다.
- 개발 의존성은 `uv`로 관리하며, 패키지 내 규칙 파일도 설치 패키지 데이터로 포함됩니다.
