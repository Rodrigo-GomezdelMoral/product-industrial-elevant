PYTHON ?= python

.PHONY: install lint type test check

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

type:
	mypy

test:
	pytest -q

check: lint type test
