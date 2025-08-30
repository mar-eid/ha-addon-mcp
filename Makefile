.PHONY: help test test-unit test-integration test-coverage lint format clean install dev-install

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev-install   - Install development dependencies"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Clean up cache and build files"
	@echo "  make run-mock      - Run server with mock data"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"

install:
	pip install -r mcp-server/requirements.txt

dev-install: install
	pip install -r test-requirements.txt

test:
	pytest tests/ -v

test-unit:
	pytest tests/ -v -m "not integration"

test-integration:
	pytest tests/ -v -m "integration"

test-coverage:
	pytest tests/ -v --cov=mcp-server --cov-report=html --cov-report=term

lint:
	flake8 mcp-server/ tests/ --max-line-length=120
	mypy mcp-server/ --ignore-missing-imports
	black --check mcp-server/ tests/

format:
	black mcp-server/ tests/
	isort mcp-server/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf *.egg-info
	rm -rf build/
	rm -rf dist/

run-mock:
	cd mcp-server && python server.py

docker-build:
	docker build -t ha-mcp-server ./mcp-server \
		--build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19

docker-run:
	docker run --rm -it \
		-e PGHOST=localhost \
		-e PGPORT=5432 \
		-e PGDATABASE=homeassistant \
		-e PGUSER=homeassistant \
		-e PGPASSWORD="" \
		ha-mcp-server

# Development helpers
watch-test:
	pytest-watch tests/ -v

debug-test:
	pytest tests/ -v -s --pdb

profile-test:
	pytest tests/ --profile --profile-svg

# CI/CD helpers
ci-test:
	pytest tests/ -v --cov=mcp-server --cov-report=xml --junit-xml=test-results.xml

ci-lint:
	flake8 mcp-server/ tests/ --format=junit-xml --output-file=lint-results.xml
