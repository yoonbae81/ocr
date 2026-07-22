"""Command-line entry point for sequential local document OCR."""

from __future__ import annotations

import logging
from pathlib import Path
import warnings
from time import perf_counter
from typing import Annotated

import typer

from backend_config import (
    BackendKind,
    MlxBackendConfig,
    OpenVinoBackendConfig,
)
from bootstrap import BackendConfig, open_backend
from command_runtime import RunOptions, run_source
from domain import PageNumber
from settings import load_settings


MAX_SELECTED_PAGES = 10_000
app = typer.Typer(no_args_is_help=True, add_completion=False)
_SETTINGS = load_settings()


def _normalize_library_output() -> None:
    noise_filters: tuple[tuple[str, str], ...] = (
        ("PyTorch was not found", r".*transformers\..*"),
        ("No ccache found", r".*paddle\.utils\.cpp_extension\.extension_utils"),
        (
            "'mlx-vlm-server' does not support `min_pixels`",
            r".*paddlex\.inference\.models\.doc_vlm\.predictor",
        ),
        (
            "'mlx-vlm-server' does not support `max_pixels`",
            r".*paddlex\.inference\.models\.doc_vlm\.predictor",
        ),
    )
    for message, module in noise_filters:
        warnings.filterwarnings(
            "ignore",
            message=f"{message}.*",
            category=UserWarning,
            module=module,
        )

    for logger_name in (
        "paddle",
        "paddle.utils",
        "paddle.utils.cpp_extension",
        "paddlex",
        "paddlex.inference",
        "paddleocr",
        "transformers",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _format_selected_pages(pages: tuple[PageNumber, ...] | None) -> str:
    if pages is None:
        return "all pages"
    if not pages:
        return "no pages"
    first = pages[0].value
    last = pages[-1].value
    if first == last:
        return f"page {first}"
    return f"pages {first}-{last} (total {len(pages)})"


def _parse_pages(value: str | None) -> tuple[PageNumber, ...] | None:
    if value is None:
        return None

    pages: set[int] = set()
    try:
        for item in value.split(","):
            bounds = item.strip().split("-", maxsplit=1)
            start = int(bounds[0])
            end = int(bounds[-1])
            if start < 1:
                raise typer.BadParameter("Page numbers start at 1.")
            if start > end:
                raise typer.BadParameter("Page ranges must be ascending.")
            if end - start + 1 > MAX_SELECTED_PAGES:
                raise typer.BadParameter(
                    f"A page selection is limited to {MAX_SELECTED_PAGES} pages."
                )
            pages.update(range(start, end + 1))
            if len(pages) > MAX_SELECTED_PAGES:
                raise typer.BadParameter(
                    f"A page selection is limited to {MAX_SELECTED_PAGES} pages."
                )
    except ValueError:
        raise typer.BadParameter(
            "Pages must use positive numbers, commas, and ascending ranges."
        ) from None
    return tuple(PageNumber(number) for number in sorted(pages))


def _resolve_sources(source: str) -> tuple[Path, ...]:
    if any(token in source for token in ("*", "?", "[")):
        pattern = Path(source).expanduser()
        if pattern.is_absolute():
            root = Path(pattern.anchor)
            relative_pattern = pattern.relative_to(root)
        else:
            root = Path.cwd()
            relative_pattern = pattern
        matches = tuple(
            path.resolve()
            for path in sorted(root.glob(str(relative_pattern)))
            if path.is_file()
        )
        if not matches:
            raise typer.BadParameter(f"No sources matched pattern: {source}")
        stems = [path.stem for path in matches]
        if len(stems) != len(set(stems)):
            raise typer.BadParameter(
                "Matched sources must have unique filenames before their extensions."
            )
        return matches
    resolved = Path(source).expanduser().resolve()
    if not resolved.exists():
        raise typer.BadParameter(f"Source does not exist: {source}")
    if resolved.is_dir():
        raise typer.BadParameter(f"Directories are not supported: {source}")
    return (resolved,)


def _backend_config(
    backend: BackendKind,
    model: str,
    server_url: str | None,
    vl_concurrency: int | None,
    vlm_model_path: Path | None,
    layout_model_path: Path | None,
    vlm_device: str,
    layout_device: str,
    llm_int4_compress: bool,
    vision_int8_quant: bool,
    vlm_batch_size: int,
    max_new_tokens: int,
    gpu_kv_cache_precision: str,
    model_cache_dir: Path | None,
) -> BackendConfig:
    if backend is BackendKind.MLX:
        if vlm_model_path is not None or layout_model_path is not None:
            raise typer.BadParameter(
                "OpenVINO model paths cannot be used with the MLX backend."
            )
        return MlxBackendConfig(model, server_url, vl_concurrency)
    if server_url is not None or vl_concurrency is not None:
        raise typer.BadParameter(
            "--server-url and --vl-concurrency are only valid for MLX."
        )
    if vlm_model_path is None:
        raise typer.BadParameter(
            "--vlm-model-path is required for the OpenVINO backend."
        )
    return OpenVinoBackendConfig(
        vlm_model_path=vlm_model_path.expanduser().resolve(),
        layout_model_path=(
            None
            if layout_model_path is None
            else layout_model_path.expanduser().resolve()
        ),
        vlm_device=vlm_device,
        layout_device=layout_device,
        llm_int4_compress=llm_int4_compress,
        vision_int8_quant=vision_int8_quant,
        vlm_batch_size=vlm_batch_size,
        max_new_tokens=max_new_tokens,
        gpu_kv_cache_precision=gpu_kv_cache_precision,
        model_cache_dir=(
            None
            if model_cache_dir is None
            else model_cache_dir.expanduser().resolve()
        ),
    )


@app.command()
def run(
    source: Annotated[
        str, typer.Argument(help="Input file path or wildcard pattern, e.g. '*.pdf'.")
    ],
    pages: Annotated[
        str | None, typer.Argument(help="Pages, such as 1,5-8.")
    ] = None,
    dpi: Annotated[int, typer.Option(min=72)] = 300,
    zip_filename_prefix: Annotated[
        str | None,
        typer.Option(
            "--zip-prefix",
            help="Filename prefix used to disambiguate ZIP image pages.",
        ),
    ] = None,
    replace: Annotated[bool, typer.Option(help="Overwrite existing page exports.")] = False,
    resume: Annotated[bool, typer.Option(help="Skip page exports that already exist.")] = False,
    batch_size: Annotated[
        int, typer.Option(min=1, help="Pages submitted to one Paddle queue batch.")
    ] = 4,
    use_cache: Annotated[
        bool, typer.Option("--cache/--no-cache", help="Reuse raw OCR results.")
    ] = True,
    cache_dir: Annotated[Path | None, typer.Option(help="Raw OCR cache directory.")] = None,
    backend: Annotated[
        BackendKind,
        typer.Option(help="Recognition backend: mlx or openvino."),
    ] = _SETTINGS.backend,
    model: Annotated[
        str,
        typer.Option(help="MLX-VLM model name."),
    ] = _SETTINGS.model,
    server_url: Annotated[
        str | None, typer.Option(help="Reuse an already-running MLX-VLM server.")
    ] = _SETTINGS.server_url,
    vl_concurrency: Annotated[
        int | None, typer.Option(min=1, help="Maximum concurrent VL requests.")
    ] = _SETTINGS.vl_concurrency,
    vlm_model_path: Annotated[
        Path | None,
        typer.Option(help="OpenVINO PaddleOCR-VL model directory."),
    ] = _SETTINGS.vlm_model_path,
    layout_model_path: Annotated[
        Path | None,
        typer.Option(help="Optional OpenVINO DocLayout model XML path."),
    ] = _SETTINGS.layout_model_path,
    vlm_device: Annotated[
        str, typer.Option(help="OpenVINO VLM device (GPU, CPU, or AUTO).")
    ] = _SETTINGS.vlm_device,
    layout_device: Annotated[
        str, typer.Option(help="OpenVINO layout device (CPU, GPU, NPU, or AUTO).")
    ] = _SETTINGS.layout_device,
    llm_int4_compress: Annotated[
        bool,
        typer.Option(
            "--llm-int4-compress/--no-llm-int4-compress",
            help="Select the OpenVINO INT4 LLM artifacts.",
        ),
    ] = _SETTINGS.llm_int4_compress,
    vision_int8_quant: Annotated[
        bool,
        typer.Option(
            "--vision-int8-quant/--no-vision-int8-quant",
            help="Select the OpenVINO INT8 vision artifacts.",
        ),
    ] = _SETTINGS.vision_int8_quant,
    vlm_batch_size: Annotated[
        int,
        typer.Option(min=1, help="OpenVINO VLM layout-block batch size."),
    ] = _SETTINGS.vlm_batch_size,
    max_new_tokens: Annotated[
        int,
        typer.Option(min=1, help="Maximum generated tokens per OpenVINO block."),
    ] = _SETTINGS.max_new_tokens,
    gpu_kv_cache_precision: Annotated[
        str,
        typer.Option(help="OpenVINO GPU KV-cache precision."),
    ] = _SETTINGS.gpu_kv_cache_precision,
    model_cache_dir: Annotated[
        Path | None,
        typer.Option(help="Model download cache used by the OpenVINO pipeline."),
    ] = _SETTINGS.model_cache_dir,
    profile: Annotated[bool, typer.Option(help="Print phase-level elapsed times.")] = False,
) -> None:
    """Recognize selected pages from one or more local document sources."""
    resolved_sources = _resolve_sources(source)
    _normalize_library_output()
    selected_pages = _parse_pages(pages)
    recognition_config = _backend_config(
        backend,
        model,
        server_url,
        vl_concurrency,
        vlm_model_path,
        layout_model_path,
        vlm_device,
        layout_device,
        llm_int4_compress,
        vision_int8_quant,
        vlm_batch_size,
        max_new_tokens,
        gpu_kv_cache_precision,
        model_cache_dir,
    )
    typer.echo(
        f"Starting OCR for {len(resolved_sources)} source(s) and "
        f"{_format_selected_pages(selected_pages)}."
    )
    options = RunOptions(
        pages=selected_pages,
        dpi=dpi,
        zip_filename_prefix=zip_filename_prefix,
        replace=replace,
        resume=resume,
        batch_size=batch_size,
        use_cache=use_cache,
        cache_dir=cache_dir,
        profile=profile,
    )
    total_exported = 0
    failures: list[tuple[Path, Exception]] = []
    with open_backend(recognition_config, typer.echo) as recognition_backend:
        for index, resolved in enumerate(resolved_sources, start=1):
            typer.echo(f"[{index}/{len(resolved_sources)}] Source: {resolved.name}")
            started = perf_counter()
            try:
                exported_pages = run_source(resolved, options, recognition_backend)
                total_exported += exported_pages
                elapsed = perf_counter() - started
                typer.echo(
                    f"[{index}/{len(resolved_sources)}] Source completed: {resolved.name}, "
                    f"{exported_pages} page(s) in {elapsed:.3f}s"
                )
            except (OSError, RuntimeError, ValueError) as error:
                elapsed = perf_counter() - started
                typer.echo(
                    f"[{index}/{len(resolved_sources)}] Source failed: {resolved.name} "
                    f"after {elapsed:.3f}s: {error}",
                    err=True,
                )
                failures.append((resolved, error))
                continue
    if len(resolved_sources) > 1:
        typer.echo(
            f"Exported a total of {total_exported} page(s) "
            f"from {len(resolved_sources)} source(s)."
        )
    if failures:
        typer.echo(
            f"Failed to process {len(failures)} of {len(resolved_sources)} source(s).",
            err=True,
        )
        raise typer.Exit(code=1)


def main() -> None:
    """Run the OCR command-line application."""
    app()
