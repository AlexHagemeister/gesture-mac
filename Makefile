# The gnadd workflow runs `make test` when a Makefile has the target, so
# tests run inside the uv venv rather than whatever pytest is on PATH.
.PHONY: test
test:
	uv run pytest -q
