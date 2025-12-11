.PHONY: help check-uv dev-setup test-setup test test-all test-unit test-integration clean ui-test ui-build ui-lint install-playwright

# Check if uv is installed
check-uv:
	@which uv > /dev/null || (echo "Error: 'uv' is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)

# Default target
help:
	@echo "Solace Agent Mesh - Dev Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make dev-setup          Set up development environment with Python 3.12"
	@echo "  make test-setup         Install all test dependencies (mirrors CI setup)"
	@echo "  make install-playwright Install Playwright browsers"
	@echo ""
	@echo "Backend Tests:"
	@echo "  make test              Run all tests (excluding stress/long_soak)"
	@echo "  make test-all          Run all tests including stress tests"
	@echo "  make test-unit         Run unit tests only"
	@echo "  make test-integration  Run integration tests only"
	@echo ""
	@echo "Frontend Tests:"
	@echo "  make ui-test           Run frontend linting and build"
	@echo "  make ui-lint           Run frontend linting only"
	@echo "  make ui-build          Build frontend packages"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             Clean up test artifacts and cache"
	@echo ""

# Set up development environment
dev-setup: check-uv
	@echo "Setting up development environment..."
	UV_VENV_CLEAR=1 uv venv --python 3.12
	@echo "Syncing dependencies with all extras..."
	uv sync --all-extras
	@echo "Installing test infrastructure..."
	uv pip install -e tests/sam-test-infrastructure
	@echo "Installing Playwright browsers..."
	uv run playwright install
	@echo "Development environment setup complete!"
	@echo "To activate the virtual environment, run: source .venv/bin/activate"

# Setup test environment 
test-setup: check-uv
	@echo "Installing test dependencies..."
	uv pip install -e ".[gcs,vertex,employee_tools,test]"
	uv pip install -e tests/sam-test-infrastructure
	@echo "Installing Playwright browsers..."
	uv run playwright install
	@echo "Test environment setup complete!"

# Install Playwright browsers only
install-playwright: check-uv
	@echo "Installing Playwright browsers..."
	uv run playwright install

# Run tests excluding stress and long_soak (default for development)
test:
	@echo "Running tests (excluding stress and long_soak)..."
	uv run pytest -m "not stress and not long_soak"

# Run all tests
test-all:
	@echo "Running all tests..."
	uv run pytest


# Run unit tests only
test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit -v

# Run integration tests only
test-integration:
	@echo "Running integration tests..."
	uv run pytest tests/integration -v

# Frontend linting (mirrors ui-ci.yml)
ui-lint:
	@echo "Running frontend linting..."
	cd client/webui/frontend && npm run lint

# Build frontend packages (mirrors ui-ci.yml)
ui-build:
	@echo "Building frontend packages..."
	cd client/webui/frontend && npm run build-package
	cd client/webui/frontend && npm run build-storybook

# Run frontend tests (lint + build)
ui-test: ui-lint ui-build
	@echo "Frontend tests completed!"

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleanup complete!"
