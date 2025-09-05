# Makefile for lock-trace project

# Project configuration
PROJECT_NAME = lock-trace
PYTHON = python3
UV = uv
PYINSTALLER = pyinstaller

# Directories
SRC_DIR = lock_trace
BUILD_DIR = build
DIST_DIR = dist
SPEC_FILE = $(PROJECT_NAME).spec

# Binary output
BINARY_NAME = lock-trace
BINARY_PATH = $(DIST_DIR)/$(BINARY_NAME)

# Default target
.PHONY: all
all: binary

# Help target
.PHONY: help
help:
	@echo "Lock-Trace Build System"
	@echo "======================"
	@echo ""
	@echo "Available targets:"
	@echo "  help        - Show this help message"
	@echo "  install     - Install dependencies using uv"
	@echo "  install-dev - Install development dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code"
	@echo "  binary      - Build standalone binary executable"
	@echo "  package     - Build Python package"
	@echo "  clean       - Clean build artifacts"
	@echo "  clean-all   - Clean all generated files"
	@echo "  run         - Run the application directly"
	@echo ""
	@echo "Binary compilation examples:"
	@echo "  make binary              - Build binary in dist/"
	@echo "  make install-binary      - Install binary to /usr/local/bin"
	@echo "  make binary-portable     - Build portable binary with dependencies"

# Dependencies installation
.PHONY: install
install:
	$(UV) sync

.PHONY: install-dev
install-dev:
	$(UV) sync --group dev
	$(UV) add --group dev pyinstaller

# Development targets
.PHONY: test
test:
	$(UV) run pytest

.PHONY: lint
lint:
	$(UV) run ruff check .
	$(UV) run black --check .

.PHONY: format
format:
	$(UV) run black .
	$(UV) run ruff check --fix .

# Run application
.PHONY: run
run:
	$(UV) run python -m lock_trace.cli $(ARGS)

# Binary compilation targets
.PHONY: binary
binary: install-dev
	@echo "Building standalone binary..."
	$(UV) run $(PYINSTALLER) \
		--name $(BINARY_NAME) \
		--onefile \
		--console \
		--clean \
		--noconfirm \
		--add-data "$(SRC_DIR):$(SRC_DIR)" \
		--hidden-import pkg_resources \
		--hidden-import pkg_resources.py2_warn \
		lock_trace/__main__.py
	@echo "Binary built successfully: $(BINARY_PATH)"
	@echo "Test the binary: ./$(BINARY_PATH) --help"

.PHONY: binary-portable
binary-portable: install-dev
	@echo "Building portable binary with dependencies..."
	$(UV) run $(PYINSTALLER) \
		--name $(BINARY_NAME)-portable \
		--onedir \
		--console \
		--clean \
		--noconfirm \
		--add-data "$(SRC_DIR):$(SRC_DIR)" \
		--collect-all lock_trace \
		--hidden-import pkg_resources \
		--hidden-import pkg_resources.py2_warn \
		lock_trace/cli.py
	@echo "Portable binary built: $(DIST_DIR)/$(BINARY_NAME)-portable/"

.PHONY: binary-debug
binary-debug: install-dev
	@echo "Building debug binary with verbose output..."
	$(UV) run $(PYINSTALLER) \
		--name $(BINARY_NAME)-debug \
		--onefile \
		--console \
		--debug all \
		--clean \
		--noconfirm \
		lock_trace/cli.py

# Installation targets
.PHONY: install-binary
install-binary: binary
	@echo "Installing binary to /usr/local/bin..."
	sudo cp $(BINARY_PATH) /usr/local/bin/
	sudo chmod +x /usr/local/bin/$(BINARY_NAME)
	@echo "Binary installed. You can now run: $(BINARY_NAME) --help"

.PHONY: uninstall-binary
uninstall-binary:
	@echo "Removing binary from /usr/local/bin..."
	sudo rm -f /usr/local/bin/$(BINARY_NAME)

# Package building
.PHONY: package
package:
	$(UV) build

# Testing targets
.PHONY: test-binary
test-binary: binary
	@echo "Testing binary executable..."
	./$(BINARY_PATH) --help
	@echo "Binary test completed successfully"

.PHONY: test-all
test-all: test lint test-binary

# Cleaning targets
.PHONY: clean
clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(DIST_DIR)
	rm -f $(SPEC_FILE)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.PHONY: clean-all
clean-all: clean
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf *.egg-info
	$(UV) cache clean

# Development workflow
.PHONY: dev-setup
dev-setup: install-dev
	@echo "Development environment setup complete"
	@echo "Run 'make test' to verify installation"

.PHONY: ci
ci: install-dev lint test binary test-binary
	@echo "CI pipeline completed successfully"

# Static binary (experimental)
.PHONY: binary-static
binary-static: install-dev
	@echo "Building static binary (experimental)..."
	$(UV) run $(PYINSTALLER) \
		--name $(BINARY_NAME)-static \
		--onefile \
		--console \
		--clean \
		--noconfirm \
		--strip \
		--noupx \
		--exclude-module tkinter \
		--exclude-module matplotlib \
		--exclude-module numpy \
		lock_trace/cli.py

# Check dependencies
.PHONY: check-deps
check-deps:
	@echo "Checking system dependencies..."
	@which $(UV) > /dev/null || (echo "Error: uv not found. Install from https://docs.astral.sh/uv/" && exit 1)
	@which $(PYTHON) > /dev/null || (echo "Error: Python 3 not found" && exit 1)
	@which cscope > /dev/null || (echo "Warning: cscope not found. Install cscope for runtime functionality")
	@echo "Dependencies check completed"

# Version info
.PHONY: version
version:
	@echo "Lock-Trace Build Information"
	@echo "============================"
	@echo "Project: $(PROJECT_NAME)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "UV: $$($(UV) --version)"
	@if [ -f "$(BINARY_PATH)" ]; then \
		echo "Binary: $(BINARY_PATH) ($$(stat -f%z $(BINARY_PATH) 2>/dev/null || stat -c%s $(BINARY_PATH) 2>/dev/null || echo 'unknown') bytes)"; \
	else \
		echo "Binary: Not built"; \
	fi

# Quick development commands
.PHONY: quick-test
quick-test:
	$(UV) run python -c "from lock_trace.cli import main; print('Module import successful')"

.PHONY: debug
debug:
	$(UV) run python -c "import lock_trace; print('Package location:', lock_trace.__file__)"
