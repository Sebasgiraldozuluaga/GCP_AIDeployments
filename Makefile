# ==============================================================================
# Installation & Setup
# ==============================================================================

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync

# ==============================================================================
# Playground Targets
# ==============================================================================

# Launch local dev playground with Generative BI
playground:
	@echo "==============================================================================="
	@echo "| 🚀 Starting your agent playground with Generative BI...                     |"
	@echo "|                                                                             |"
	@echo "| 📊 Frontend con visualizaciones: http://localhost:8000/                    |"
	@echo "|                                                                             |"
	@echo "| 💡 Prueba preguntando: 'Total de compras por proveedor'                     |"
	@echo "|                                                                             |"
	@echo "| 🔍 El servidor se recargará automáticamente al cambiar archivos             |"
	@echo "==============================================================================="
	uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload

# ==============================================================================
# Local Development Commands
# ==============================================================================

# Launch local development server with hot-reload
local-backend:
	uv run uvicorn app.fast_api_app:app --host localhost --port 8000 --reload

# Launch ADK dev-ui (original, sin visualizaciones)
dev-ui:
	@echo "==============================================================================="
	@echo "| 🚀 Starting ADK dev-ui (original)...                                        |"
	@echo "|                                                                             |"
	@echo "| 📊 Dev UI: http://localhost:8501/dev-ui/                                    |"
	@echo "|                                                                             |"
	@echo "| 🔍 IMPORTANT: Select the 'app' folder to interact with your agent.          |"
	@echo "==============================================================================="
	uv run adk web . --port 8501 --reload_agents

# ==============================================================================
# Backend Deployment Targets
# ==============================================================================

# Deploy the agent remotely
# Usage: make deploy [IAP=true] [PORT=8080] - Set IAP=true to enable Identity-Aware Proxy, PORT to specify container port
deploy:
	PROJECT_ID=$$(gcloud config get-value project) && \
	gcloud beta run deploy raju-shop \
		--source . \
		--memory "4Gi" \
		--project $$PROJECT_ID \
		--region "us-central1" \
		--no-allow-unauthenticated \
		--no-cpu-throttling \
		--labels "created-by=adk" \
		--update-build-env-vars "AGENT_VERSION=$(shell awk -F'"' '/^version = / {print $$2}' pyproject.toml || echo '0.0.0')" \
		--update-env-vars \
		"COMMIT_SHA=$(shell git rev-parse HEAD)" \
		$(if $(IAP),--iap) \
		$(if $(PORT),--port=$(PORT))

# Alias for 'make deploy' for backward compatibility
backend: deploy

# ==============================================================================
# Testing & Code Quality
# ==============================================================================

# Run unit and integration tests
test:
	uv sync --dev
	uv run pytest tests/unit && uv run pytest tests/integration

# Run code quality checks (codespell, ruff, mypy)
lint:
	uv sync --dev --extra lint
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run mypy .