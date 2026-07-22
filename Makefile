UV ?= uv

.PHONY: sync sync-mlx sync-openvino configure-mlx configure-openvino install install-mlx install-openvino uninstall test lint typecheck check

sync:
	$(UV) sync --all-groups

sync-mlx:
	$(UV) sync --all-groups --extra mlx

sync-openvino:
	$(UV) sync --all-groups --extra openvino

install: install-mlx

configure-mlx: sync-mlx
	$(UV) run python -m install_config --backend mlx

configure-openvino: sync-openvino
	$(UV) run python -m install_config --backend openvino

install-mlx: configure-mlx
	$(UV) tool install --editable ".[mlx]" --force
	$(UV) tool update-shell

install-openvino: configure-openvino
	$(UV) tool install --editable ".[openvino]" --force
	$(UV) tool update-shell

uninstall:
	$(UV) tool uninstall ocr

test:
	$(UV) run pytest -q

lint:
	$(UV) run ruff check src tests

typecheck:
	$(UV) run basedpyright

check: test lint typecheck
