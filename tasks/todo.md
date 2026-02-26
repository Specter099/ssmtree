# ssmtree — Implementation Checklist

## Phase 1: Project Setup
- [x] `pyproject.toml` with runtime + dev dependencies
- [x] `.gitignore` with Python/AWS patterns
- [x] Directory structure (`src/`, `tests/`, `.github/`)

## Phase 2: Core Modules
- [x] `src/ssmtree/__init__.py` — version export
- [x] `src/ssmtree/models.py` — `Parameter`, `TreeNode` dataclasses
- [x] `src/ssmtree/fetcher.py` — `fetch_parameters()` with pagination
- [x] `src/ssmtree/tree.py` — `build_tree()` from flat list
- [x] `src/ssmtree/formatters.py` — Rich tree + diff + copy plan tables
- [x] `src/ssmtree/differ.py` — `diff_namespaces()`
- [x] `src/ssmtree/copier.py` — `copy_namespace()` with dry-run

## Phase 3: CLI
- [x] `src/ssmtree/cli.py` — Click commands: main, diff, copy

## Phase 4: Tests
- [x] `tests/fixtures/parameters.json` — sample SSM parameters
- [x] `tests/conftest.py` — moto fixtures
- [x] `tests/test_models.py`
- [x] `tests/test_fetcher.py`
- [x] `tests/test_tree.py`
- [x] `tests/test_formatters.py`
- [x] `tests/test_cli.py`
- [x] `tests/test_differ.py`
- [x] `tests/test_copier.py`

## Phase 5: CI
- [x] `.github/workflows/ci.yml` — lint + test on push/PR

## Backlog

- [x] Show `[redacted]` for `SecureString` parameter values in tree output to make it clear to the user that the value is sensitive and not displayed (unless `--decrypt` is passed)

## CLI Usage

```bash
# Install
pip install -e ".[dev]"

# Show tree at root
ssmtree /

# Show specific namespace with decryption
ssmtree --decrypt /app/prod

# Filter parameters
ssmtree --filter "*db*" /app

# Diff two namespaces
ssmtree diff /app/prod /app/staging

# Copy namespace (dry run first)
ssmtree copy --dry-run /app/prod /app/staging
ssmtree copy --overwrite /app/prod /app/staging
```
