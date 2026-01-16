# Default target
.PHONY: all
all: configure lint type-check run-tests pipeline

.PHONY: fmt
fmt:
	@echo "Running Ruff Format on Python scripts and Notebooks..."
	uv run ruff format ./src

.PHONY: fmt-check
fmt-check:
	@echo "Running Ruff Format check on Python scripts and Notebooks..."
	uv run ruff format ./src --check

.PHONY: lint
lint:
	@echo "Running Ruff for linting python code..."
	uv run ruff check .

.PHONY: lint-notebooks
lint-notebooks:
	@echo "Running Ruff for linting python Notebooks..."
	uv run nbqa ruff ./src

# Type checking using Mypy
.PHONY: type-check
type-check:
	@echo "Running Mypy for type checking..."
	uv run mypy ./src

.PHONY: type-check-notebooks
type-check-notebooks:
	@echo "Running Mypy for type checking..."
	uv run nbqa mypy ./src

# Running tests with Pytest and generating coverage report
.PHONY: run-tests
run-tests:
	@echo "Running Pytest with coverage..."
	uv run pytest --cov=./src/extraction_service .


# Cleaning up build artifacts
.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf .pytest_cache .mypy_cache .ipynb_checkpoints .coverage
	find . -name "__pycache__" -exec rm -rf {} +

# Check everything
.PHONY: check-all
check-all: fmt-check lint lint-notebooks type-check type-check-notebooks run-tests
	@echo "Full pipeline completed successfully!"
