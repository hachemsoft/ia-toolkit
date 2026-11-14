# Python

Standard: PEP 8 (style), PEP 257 (docstrings), PEP 484 (type hints), as the repo applies them.

Tools: the repo's environment (poetry, uv, pip-tools, conda), never a new one; its formatter and linter (ruff, black, flake8, isort) and type checker (mypy, pyright) when declared; its test runner (pytest or unittest). Do not add one.

Classic traps:
- A mutable default argument (`def f(x=[])`).
- Naive and timezone-aware `datetime` mixed or compared.
- A bare `except:` or `except Exception: pass` that hides errors.
- Dependencies declared in one place only (`pyproject.toml` or `requirements*.txt`, as the repo does), with its lock file updated by its tool.
- Tests sharing mutable module state, so their order changes the result; use fixtures that reset it.
- An import with side effects at module level (network, file writes) that runs on import.
