.PHONY: install test lint format ci help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-10s %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	pip install -e ".[dev]"

test: ## Run tests with coverage
	pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80

lint: ## Run ruff, black and mypy checks
	ruff check src/ tests/
	black --check src/ tests/
	mypy src/check_netscaler_gateway/

format: ## Format code with black and fix ruff findings
	black src/ tests/
	ruff check --fix src/ tests/

ci: lint test ## Run all CI checks
