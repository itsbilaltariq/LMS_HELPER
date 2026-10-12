.PHONY: dev test lint format check

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/ -v

lint:
	ruff check .
	mypy app/

format:
	ruff format .
