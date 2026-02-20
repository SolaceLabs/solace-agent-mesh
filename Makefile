.PHONY: help check-uv dev-setup test-setup test test-all test-eval test-eval-local test-eval-workflow test-eval-remote test-unit test-integration clean ui-test ui-build ui-lint install-playwright

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
	@echo "  make test                Run all tests (excluding stress/long_soak)"
	@echo "  make test-all            Run all tests including stress and evaluation tests"
	@echo "  make test-eval           Run local evaluation tests (default)"
	@echo "  make test-eval-local     Run local evaluation tests"
	@echo "  make test-eval-workflow  Run workflow evaluation tests"
	@echo "  make test-eval-remote    Run remote evaluation tests"
	@echo "  make test-unit           Run unit tests only"
	@echo "  make test-integration    Run integration tests only"
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

# Setup eval environment
# Note: Uses wheel build instead of editable install because hatchling's editable mode
# doesn't support force-include for cli/, evaluation/, etc. directories outside src/
eval-setup: check-uv
	@echo "Setting up evaluation test environment..."
	UV_VENV_CLEAR=1 uv venv --python 3.12
	@echo "Building wheel directly (skipping UI builds and sdist for speed)..."
	SAM_SKIP_UI_BUILD=true uv build --wheel
	@echo "Installing Solace Agent Mesh from wheel..."
	uv pip install "$$(ls dist/solace_agent_mesh-*.whl | head -1)" --reinstall
	@echo "Installing sam-rest-gateway plugin for local evaluations..."
	uv pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"
	@echo "Installing Playwright browsers..."
	.venv/bin/playwright install

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

# Helper target to validate required environment variables
check-eval-env:
	@echo "Validating required environment variables..."
	@test -n "$(SOLACE_BROKER_URL)" || (echo "ERROR: SOLACE_BROKER_URL not set. Export it before running make" && exit 1)
	@test -n "$(SOLACE_BROKER_USERNAME)" || (echo "ERROR: SOLACE_BROKER_USERNAME not set. Export it before running make" && exit 1)
	@test -n "$(SOLACE_BROKER_PASSWORD)" || (echo "ERROR: SOLACE_BROKER_PASSWORD not set. Export it before running make" && exit 1)
	@test -n "$(SOLACE_BROKER_VPN)" || (echo "ERROR: SOLACE_BROKER_VPN not set. Export it before running make" && exit 1)
	@test -n "$(LLM_SERVICE_ENDPOINT)" || (echo "ERROR: LLM_SERVICE_ENDPOINT not set. Export it before running make" && exit 1)
	@test -n "$(LLM_SERVICE_API_KEY)" || (echo "ERROR: LLM_SERVICE_API_KEY not set. Export it before running make" && exit 1)
	@echo "✓ All required environment variables are set"


check-remote-eval-env:
	@echo "Validating required environment variables..."
	@test -n "$(EVAL_REMOTE_URL)" || (echo "ERROR: EVAL_REMOTE_URL not set. Export it before running make" && exit 1)
	@test -n "$(EVAL_NAMESPACE)" || (echo "ERROR: EVAL_NAMESPACE not set. Export it before running make" && exit 1)
	@test -n "$(EVAL_AUTH_TOKEN)" || (echo "ERROR: EVAL_AUTH_TOKEN not set. Export it before running make" && exit 1)
	@echo "✓ All required remote environment variables are set"

# Define env vars to pass through to eval commands
EVAL_ENV_VARS = SOLACE_BROKER_URL="$(SOLACE_BROKER_URL)" \
	SOLACE_BROKER_USERNAME="$(SOLACE_BROKER_USERNAME)" \
	SOLACE_BROKER_PASSWORD="$(SOLACE_BROKER_PASSWORD)" \
	SOLACE_BROKER_VPN="$(SOLACE_BROKER_VPN)" \
	LLM_SERVICE_ENDPOINT="$(LLM_SERVICE_ENDPOINT)" \
	LLM_SERVICE_API_KEY="$(LLM_SERVICE_API_KEY)"


# Define env vars to pass through to eval commands
REMOTE_EVAL_ENV_VARS = EVAL_REMOTE_URL="$(EVAL_REMOTE_URL)" \
	EVAL_NAMESPACE="$(EVAL_NAMESPACE)" \
	EVAL_AUTH_TOKEN="$(EVAL_AUTH_TOKEN)"

# Run evaluation tests (default: local)
test-eval: test-eval-local

# Run local evaluation tests
test-eval-local: eval-setup check-eval-env
	@echo "Running local evaluation tests..."
	@echo ""
	$(EVAL_ENV_VARS) .venv/bin/sam eval tests/evaluation/local_example.json -v

# Run workflow evaluation tests
test-eval-workflow: eval-setup check-eval-env
	@echo "Running workflow evaluation tests..."
	@echo ""
	$(EVAL_ENV_VARS) .venv/bin/sam eval tests/evaluation/workflow_eval.json

# Run remote evaluation tests
test-eval-remote: eval-setup check-eval-env check-remote-eval-env
	@echo "Running remote evaluation tests..."
	@echo ""
	$(EVAL_ENV_VARS) $(REMOTE_EVAL_ENV_VARS) .venv/bin/sam eval tests/evaluation/remote_example.json -v

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
