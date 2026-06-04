.PHONY: install test lint typecheck check clean eval eval-trend

install:
	uv pip install -e ".[dev,openai,anthropic]"

test:
	pytest tests/ -x -q

lint:
	ruff check src/open_agent/

typecheck:
	mypy src/open_agent/ --ignore-missing-imports

check: test lint typecheck
	@echo "All checks passed"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .open_agent/

eval:
	agent eval --suite smoke

eval-trend:
	agent eval-trend --suite smoke
