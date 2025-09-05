# Development Commands

## Basic Development
- **Install dependencies**: `uv sync` or `make install`
- **Install dev dependencies**: `uv sync --group dev` or `make install-dev`
- **Run tests**: `uv run pytest` or `make test`
- **Format code**: `uv run black .` or `make format`
- **Lint code**: `uv run ruff check .` or `make lint`
- **Build package**: `uv build` or `make package`

## Binary Compilation
- **Build binary**: `make binary`
- **Build portable binary**: `make binary-portable`
- **Test binary**: `make test-binary`
- **Install binary**: `make install-binary`

## Application Usage
- **Run application**: `uv run python -m lock_trace.cli` or `make run`
- **Run with arguments**: `make run ARGS="--help"`
- **Test CLI with display options**: 
  - `uv run python -m lock_trace.cli callers schedule --tree`
  - `uv run python -m lock_trace.cli lock-context my_func --verbose`
  - `uv run python -m lock_trace.cli lock-check my_func lock_var --tree`

## Quality Assurance
- **Run all tests**: `make test-all`
- **Run CI pipeline**: `make ci`
- **Check dependencies**: `make check-deps`

## Additional Commands
- **Run single test**: `uv run pytest tests/test_specific.py::test_function`
- **Code coverage**: `uv run pytest --cov=lock_trace --cov-report=html`
- **Clean build artifacts**: `make clean`
- **Clean all**: `make clean-all`
- **Development setup**: `make dev-setup`
