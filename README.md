# Local OCR

## 설치

요구사항: Python 3.13 이상, `uv`

MLX와 OpenVINO는 Transformers 버전 요구사항이 충돌하므로 동일 환경에 함께
설치하지 않고 하드웨어에 맞는 프로필 하나를 선택합니다.

### Apple Silicon MLX

```zsh
git clone <repository-url> ocr
cd ocr
make install-mlx
```

### Windows + Intel iGPU(OpenVINO)

Windows 기본 환경에는 `make`가 없을 수 있으므로 아래 PowerShell 명령으로
직접 설치하는 방법을 권장합니다.

1. `uv`가 없다면 설치하고 PowerShell을 다시 엽니다.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

WinGet 등 다른 설치 방법은 [uv 공식 설치 문서](https://docs.astral.sh/uv/getting-started/installation/)를 참고합니다.

2. 저장소를 내려받고 모델 경로를 지정합니다.

```powershell
git clone <repository-url> ocr
cd ocr
$env:OCR_VLM_MODEL_PATH="C:\models\PaddleOCR-VL-1.6-OpenVINO-INT4"
$env:OCR_LAYOUT_MODEL_PATH="C:\models\DocLayoutV3.xml"
```

`OCR_VLM_MODEL_PATH`는 필수이고 `OCR_LAYOUT_MODEL_PATH`는 선택입니다.

3. OpenVINO 환경과 실행 명령을 설치합니다.

```powershell
uv sync --all-groups --extra openvino
uv run python -m install_config --backend openvino
uv tool install --editable ".[openvino]" --force
uv tool update-shell
```

4. PowerShell을 새로 열고 전역 실행 여부를 확인합니다.

```powershell
Get-Command ocr
ocr --help
ocr C:\docs\book.pdf 1-3
```

설치가 완료되면 작업 디렉터리와 관계없이 `ocr`만 입력해 실행할 수 있습니다.
GNU Make가 설치된 환경에서는 2번까지 수행한 뒤 다음 단축 명령을 사용해도
동일하게 설치됩니다.

```powershell
make install-openvino
```

`make install`은 이전과 같이 MLX 프로필을 설치합니다. 각 설치 방법은 선택한
백엔드 의존성을 맞추고 프로젝트를 editable 모드로 등록한 뒤 실행 기본값을
사용자 설정 `.env`에 저장합니다. OpenVINO 설치 시 `OCR_VLM_MODEL_PATH`는
필수이고 `OCR_LAYOUT_MODEL_PATH`는 선택입니다.

설치 설정 위치:

- Windows: `%APPDATA%\ocr\.env`
- Linux/macOS: `~/.config/ocr/.env` (`XDG_CONFIG_HOME` 지원)

실행 시 우선순위는 CLI 옵션, 프로세스 환경변수, 현재 디렉터리 `.env`, 설치
설정 `.env`, 내장 기본값 순서입니다.

설치 명령은 현재 디렉터리 `.env`도 읽으므로 환경변수를 직접 지정하는 대신
`.env.example`을 `.env`로 복사해 모델 경로를 수정한 뒤 실행할 수도 있습니다.

## 사용법

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
- 출력 대상 폴더: 실행 디렉터리에 입력 파일명과 동일한 폴더를 만들고 페이지별로 `0001.md`, `0002.md` ... 저장
- 이미지: `img/` 하위에 본문에서 추출된 이미지 영역만 저장
  - 파일명 규칙: `<page:04d>_<start_x>_<start_y>_<end_x>_<end_y>.jpg`

예시:

```text
./book/
├── 0001.md
├── 0002.md
└── img/
    └── 0002_369_1899_1903_2660.jpg
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

```powershell
# Intel Arc iGPU + OpenVINO
ocr C:\docs\book.pdf 1-3 `
  --backend openvino `
  --vlm-model-path C:\models\PaddleOCR-VL-1.6-OpenVINO-INT4 `
  --layout-model-path C:\models\DocLayoutV3.xml
```

명령 형식: `ocr <파일/패턴> <페이지>`

옵션 요약:

- `pages`(선택 위치 인자): 생략 시 전체 페이지, 지정 시 `1,5-8` 형식
- `--dpi`: PDF 렌더링 해상도 (기본값 300)
- `--zip-prefix`: ZIP 내부 파일명 충돌 방지용 프리픽스
- `--replace`: 기존 페이지 덮어쓰기
- `--resume`: 이미 존재하는 페이지 스킵
- `--batch-size`: Paddle 페이지 배치 크기(기본 4)
- `--backend`: `mlx` 또는 `openvino` 선택(기본 `mlx`)
- `--cache/--no-cache`: OCR 원문 캐시 사용 여부(기본 사용)
- `--cache-dir`: 캐시 경로 지정
- `--server-url`, `--vl-concurrency`: MLX 전용 서버 설정
- `--vlm-model-path`, `--layout-model-path`: OpenVINO 모델 경로
- `--vlm-device`, `--layout-device`: OpenVINO 장치(권장 `GPU`/`CPU`)
- `--vlm-batch-size`: OpenVINO 레이아웃 블록 배치 크기(기본 32)
- `--max-new-tokens`: OpenVINO 블록당 생성 토큰 상한(기본 64)
- `--llm-int4-compress`, `--vision-int8-quant`: 양자화 모델 선택
- `--gpu-kv-cache-precision`: Intel GPU KV-cache 정밀도(기본 `f16`)
- `--profile`: 준비/캐시/인식/전체 시간 출력

## 아키텍처(헥사고날)

현재 구조:

- `cli.py`: `typer` CLI 진입점
- `application.py`: 페이지 선택·캐시 사용·인식 결과 기록 플로우
- `ports/recognition.py`: 인식기와 백엔드 지연 생성 포트
- `adapters/recognition/mlx.py`: MLX-VLM PaddleOCR-VL 어댑터
- `adapters/recognition/openvino.py`: 인프로세스 OpenVINO 어댑터
- `adapters/recognition/backend.py`: 백엔드 수명주기와 캐시 식별자
- `bootstrap.py`: CLI 설정을 구체 어댑터로 연결하는 조립 계층
- `mlx_server.py`: 로컬 MLX 서버 생명주기 관리
- `ports/source.py`: 입력 소스 포트(계약)
- `adapters/source/{image.py,pdf.py,zip.py}`: PDF/JPG/PNG/WEBP/ZIP 입력 구현
- `ports/cache.py`, `ports/output.py`: 포트(인터페이스)
- `adapters/cache/*`: 캐시 어댑터 (`filesystem`, `disabled`)
- `adapters/output/*`: 출력 어댑터(`markdown`)

참고:

- `paddle_adapter.py`와 `source_adapter.py`는 더 이상 루트 모듈로 존재하지 않습니다.
- 현재는 `adapters/recognition`, `adapters/source`, `ports/source`를 통해 구현이 구성되어 있습니다.

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
