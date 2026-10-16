.PHONY: install test lint format clean eval serve docker-build docker-up

install:
	pip install -e ".[dev]"

test:
	pytest tests -v

lint:
	python3 -m ruff check src tests || true

format:
	python3 -m ruff format src tests || true

eval:
	python3 scripts/run_eval.py --suite all --provider deterministic

serve:
	python3 scripts/run_local.py --mode server

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache dist build *.egg-info astra_agent.db eval_report.json

docker-build:
	docker build -t astra-agent:latest .

docker-up:
	docker compose up -d
