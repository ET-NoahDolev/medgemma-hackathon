# Documentation Makefile for gemma-hackathon
# This Makefile provides commands to build and serve the MkDocs documentation

# Ensure bash is used for shell commands (required for read -p)
SHELL := /bin/bash

.PHONY: help docs-build docs-serve clean create-component docs-openapi

# Component creation commands
.PHONY: create-component
create-component:
	@read -p "Enter component name: " COMPONENT_NAME; \
	./scripts/create_component.sh "$$COMPONENT_NAME"

# Generate components overview page
docs-components-gen:
	@echo "Generating components overview page..."
	uv run python scripts/generate_components_overview.py

# Update root navigation to include all components
docs-nav-update:
	@echo "Updating root navigation..."
	uv run python scripts/update_root_navigation.py

# Build the documentation site
docs-build: docs-nav-update docs-components-gen docs-openapi
	@echo "Building documentation site..."
	uv run mkdocs build -f mkdocs.yml

# Serve the documentation locally
docs-serve:
	@echo "Serving built documentation site..."
	@if [ ! -d "site" ]; then \
		echo "No built site found. Run 'make docs-build' first."; \
		exit 1; \
	fi
	@echo "Serving from: $(PWD)/site"
	@echo "Available at: http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	@cd site && python3 -m http.server 8000

# Export OpenAPI spec from the API service
docs-openapi:
	@echo "Exporting OpenAPI spec..."
	uv run --project components/api-service python components/api-service/scripts/export_openapi.py

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf site/
	rm -rf .cache/
	rm -rf docs/.uv_cache/

# Help target
help:
	@echo "Documentation Makefile"
	@echo ""
	@echo "Component creation:"
	@echo "  create-component      Create a new Python component"
	@echo ""
	@echo "Documentation:"
	@echo "  docs-build            Build the documentation site"
	@echo "  docs-serve            Serve the built documentation site (no rebuild)"
	@echo "  docs-components-gen   Generate components overview page"
	@echo "  docs-nav-update       Update root navigation"
	@echo "  clean                 Clean build artifacts"
