.PHONY: run run-desktop run-web run-api lint test test-verbose test-coverage install clean
run: run-desktop

run-desktop:
	APP_MODE=desktop python run.py

run-web:
	APP_MODE=web python run.py

run-api:
	APP_MODE=api python run.py

test:
	pytest -q

test-verbose:
	pytest -v

test-coverage:
	pytest --cov=src --cov-report=html --cov-report=term

install:
	pip install -r requirements.txt

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/ .pytest_cache/ .coverage dist/ build/ *.egg-info
