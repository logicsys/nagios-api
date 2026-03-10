include vars.env

RELEASE ?= 1
RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
BUILD_STAMP := .build.stamp
BUILD_DEPS := Dockerfile.dev requirements.txt vars.env setup.py nagios/__init__.py nagios/core.py

.PHONY: help build lint test audit deb rpm packages clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  build   Build the dev container image"
	@echo "  lint    Run flake8 linter"
	@echo "  test    Run pytest"
	@echo "  audit   Audit dependencies for vulnerabilities"
	@echo "  deb      Build .deb package"
	@echo "  rpm      Build .rpm package"
	@echo "  packages Build both .deb and .rpm packages"
	@echo "  clean   Remove the dev container image"
	@echo ""
	@echo "Override version/release: make deb VERSION=2.0.0 RELEASE=3"

$(BUILD_STAMP): $(BUILD_DEPS)
	scripts/build.sh
	@touch $@

build: $(BUILD_STAMP)

lint: $(BUILD_STAMP)
	scripts/lint.sh

test: $(BUILD_STAMP)
	scripts/test.sh

audit: $(BUILD_STAMP)
	scripts/audit.sh

deb:
	scripts/build-deb.sh $(VERSION) $(RELEASE)

rpm:
	scripts/build-rpm.sh $(VERSION) $(RELEASE)

packages: deb rpm

clean:
	$(RUNTIME) rmi $(IMAGE) 2>/dev/null || true
	@rm -f $(BUILD_STAMP)
