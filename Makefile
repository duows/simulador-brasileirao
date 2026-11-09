PY ?= .venv/Scripts/python

.PHONY: check
check:
	$(PY) scripts/check.py
