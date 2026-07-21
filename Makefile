UV ?= uv

.PHONY: sync install uninstall test lint typecheck check

sync:
	$(UV) sync --all-groups

install: sync
	$(UV) tool install --editable . --force
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
