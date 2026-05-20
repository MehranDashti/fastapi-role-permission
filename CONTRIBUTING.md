# Contributing

Thank you for your interest in contributing to `fastapi-role-permission`!

## Development setup

```bash
git clone https://github.com/MehranDashti/fastapi-role-permission
cd fastapi-role-permission
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

For coverage:

```bash
pytest tests/ --cov=fastapi_role_permission --cov-report=term-missing
```

## Code style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and import sorting.

```bash
ruff check .
ruff format .
```

Optional: install the pre-commit hooks so these run automatically on every commit.

```bash
pip install pre-commit
pre-commit install
```

## Submitting changes

1. Fork the repository and create a feature branch from `main`.
2. Write tests for any new functionality — aim to keep coverage above 90%.
3. Run `pytest` and `ruff check .` and confirm both pass.
4. Open a pull request with a clear description of *what* and *why*.

## Reporting bugs

Please open a GitHub issue and include:
- Python version
- Package version (`pip show fastapi-role-permission`)
- A minimal reproducer
- The full traceback

## Design principles

- **Auth-agnostic**: the package never touches JWT or sessions; it only checks roles and permissions.
- **SQLAlchemy-first**: all state lives in the database; Redis/memory is a read cache only.
- **No new dependencies**: prefer standard library over third-party for optional features.
- **Backward-compatible**: avoid breaking changes within a major version.
