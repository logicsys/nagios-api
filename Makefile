include vars.env

RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

.PHONY: help build lint test clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  build   Build the dev container image"
	@echo "  lint    Run flake8 linter"
	@echo "  test    Run pytest"
	@echo "  clean   Remove the dev container image"

build:
	scripts/build.sh

lint:
	scripts/lint.sh

test:
	scripts/test.sh

clean:
	$(RUNTIME) rmi $(IMAGE) 2>/dev/null || true
