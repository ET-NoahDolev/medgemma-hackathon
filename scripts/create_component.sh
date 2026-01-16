#!/bin/bash

# This script initializes a new component with the provided name.
set -e

# Check for required tools
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required but not installed."
    echo "Install it from: https://github.com/astral-sh/uv"
    exit 1
fi

COMPONENT=$1

if [ -z "$COMPONENT" ]; then
    echo "Usage: $0 <COMPONENT>"
    exit 1
fi


# Check if component contains only valid characters (lowercase letters and hyphens, no spaces or numbers)
if ! [[ "$COMPONENT" =~ ^[a-z-]+$ ]]; then
    echo "Error: Component name can only contain lowercase letters and hyphens, no spaces or numbers."
    exit 1
fi

echo "Valid component name and folder!"
echo "🔧 Configuring the component with UV..."
# Initialize the component using UV
uv init --name $COMPONENT --package --python 3.12 components/$COMPONENT
cd components/$COMPONENT
# Format package folder name replacing - by _
PACKAGE=$(echo "$COMPONENT" | awk '{gsub("-", "_"); print}')

# Adding mandatory dependencies
uv add ruff mypy pytest pytest-cov ipykernel nbqa pre-commit --dev

echo "✅ Lint, test and docs group dependencies has been successfully configured for component '$COMPONENT'."

echo "🔧 Creating some code placeholders in the component..."

# Create directories and files
mkdir -p "src/$PACKAGE/notebooks"
mkdir -p "src/$PACKAGE/internal"
touch "src/$PACKAGE/notebooks/.gitkeep"
touch "src/$PACKAGE/internal/__init__.py"
touch "Dockerfile"
mkdir -p "tests"
echo '' > src/$PACKAGE/__init__.py

# Add example function
cat <<EOF > "src/$PACKAGE/example.py"
def example_function(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a (int): First number.
        b (int): Second number.

    Returns:
        int: Sum of the two numbers.

    Examples:
        >>> example_function(2, 3)
        5
    """
    return a + b

EOF
cat <<EOF > "src/$PACKAGE/main.py"
from $PACKAGE.example import example_function


def main() -> None:
    """Execute the main logic of the component.

    Args:
        None
    Returns:
        None

    Examples:
        >>> main()
    """
    print("Component A is running.")
    example_function(1,2)

if __name__ == "__main__":
    main()

EOF
# Add example test
cat <<EOF > "tests/test_example.py"
from $PACKAGE.example import example_function


def test_example_function():
    assert example_function(2, 3) == 5
    assert example_function(-1, 1) == 0
    assert example_function(0, 0) == 0

EOF

echo "✅ Code examples has been successfully configured for component '$COMPONENT'."

echo "🔧 Configuring the pyproject.toml rules..."
# Append Ruff and Mypy configurations to pyproject.toml
cat <<EOF >> "pyproject.toml"
[tool.ruff]
lint.select = ["E", "F", "W", "C", "N", "I", "D"]
lint.ignore = ["E203", "D203", "D213", "D100", "D413", "D104"]
target-version = "py312"
line-length = 88
exclude = ["venv", ".venv", "tests", "docs"]
lint.pydocstyle.convention = "google"

[tool.mypy]
strict = true
exclude = ["venv", ".venv", "tests", "docs"]
plugins = []

[tool.pytest.ini_options]
pythonpath = [
  "src"
]

[tool.uv]
cache-dir = "./.uv_cache"

EOF

echo "✅ pyproject.toml has been successfully configured for component '$COMPONENT'."

echo "🔧 Generating your Makefile..."
# Add component-specific Makefile
cat <<EOF > "Makefile"
# Default target
.PHONY: all
all: configure lint type-check run-tests pipeline

.PHONY: fmt
fmt:
	@echo "✨ Running Ruff Format on Python scripts and Notebooks..."
	uv run ruff format ./src

.PHONY: fmt-check
fmt-check:
	@echo "✨ Running Ruff Format check on Python scripts and Notebooks..."
	uv run ruff format ./src --check

.PHONY: lint
lint:
	@echo "✨ Running Ruff for linting python code..."
	uv run ruff check .

.PHONY: lint-notebooks
lint-notebooks:
	@echo "✨ Running Ruff for linting python Notebooks..."
	uv run nbqa ruff ./src

# Type checking using Mypy
.PHONY: type-check
type-check:
	@echo "🔍 Running Mypy for type checking..."
	uv run mypy ./src

.PHONY: type-check-notebooks
type-check-notebooks:
	@echo "🔍 Running Mypy for type checking..."
	uv run nbqa mypy ./src

# Running tests with Pytest and generating coverage report
.PHONY: run-tests
run-tests:
	@echo "🧪 Running Pytest with coverage..."
	uv run pytest --cov=./src/$PACKAGE .


# Cleaning up build artifacts
.PHONY: clean
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf .pytest_cache .mypy_cache .ipynb_checkpoints .coverage
	find . -name "__pycache__" -exec rm -rf {} +

# Check everything
.PHONY: check-all
check-all: fmt-check lint lint-notebooks type-check type-check-notebooks run-tests
	@echo "✅ Full pipeline completed successfully!"

EOF

echo "✅ Project Makefile has been successfully configured for component '$COMPONENT'."

echo "🔧 Setting up MkDocs for documentation integration..."
# Create mkdocs.yml for documentation integration
cat <<EOF > "mkdocs.yml"
docs_dir: .
site_name: $COMPONENT
nav:
  - Home: README.md
  - Code Documentation:
      API Reference: ${COMPONENT}/docs/api
EOF

# Create API documentation directory and file
mkdir -p "docs/api"
cat <<EOF > "docs/api/index.md"
# $COMPONENT API Reference

This page contains automatically generated API documentation for the $COMPONENT component.

## API Documentation

::: $PACKAGE
    handler: python
    selection:
      docstring_style: google
    rendering:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      show_signature_annotations: true
      show_bases: true
      heading_level: 3
      members_order: source
      filters: ["!^_"]
      merge_init_into_class: true
      show_if_no_docstring: false
      separate_signature: true
      signature_crossrefs: true
      show_submodules: true
      show_inheritance_diagram: true
      show_root_toc_entry: true
EOF

echo "✅ MkDocs and API documentation have been configured for documentation integration."
echo ""
echo "✅ Component '$COMPONENT' has been initialized successfully in '$COMPONENT'."
echo ""
echo "🚀 Next steps:"
echo "   1. cd components/$COMPONENT"
echo "   2. Edit pyproject.toml with your description and authors"
echo "   3. uv sync"
echo "   4. make check-all"
echo "   5. The component is ready for documentation integration!"
