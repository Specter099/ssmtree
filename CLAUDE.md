# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool for browsing, diffing, copying, and writing AWS SSM Parameter Store parameters as a colorized terminal tree. Built with Click, Rich, and boto3. Published to PyPI as `ssmtree`.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Common Commands

```
# Lint
.venv/bin/ruff check src tests

# Type checking
.venv/bin/mypy src

# Run tests with coverage
.venv/bin/pytest --cov=ssmtree --cov-report=term-missing

# Format check
.venv/bin/black --check src tests

# Dependency audit
.venv/bin/pip-audit
```

## Directory Structure

```
src/ssmtree/
├── cli.py          # Click CLI entry point (main group + diff/copy/put subcommands)
├── models.py       # Parameter and TreeNode dataclasses
├── fetcher.py      # SSM API calls (get_parameters_by_path pagination)
├── tree.py         # Build/filter tree from flat parameter list
├── differ.py       # Diff two SSM namespaces (added/removed/changed)
├── copier.py       # Copy parameters between namespaces
├── putter.py       # Write a single parameter
└── formatters.py   # Rich rendering (tree, diff table, copy plan)
tests/
├── conftest.py     # Shared fixtures (moto SSM mock)
├── fixtures/       # Test data JSON files
└── test_*.py       # One test module per source module
```

## Architecture

The CLI supports two invocation styles: `ssmtree [PATH]` for tree display, and `ssmtree <subcommand>` for diff/copy/put. A custom `_DefaultPathGroup` in `cli.py` handles routing between these modes.

Data flow: `fetcher` → `models.Parameter` list → `tree.build_tree()` → `TreeNode` hierarchy → `formatters.render_tree()` → Rich output. SecureString values are redacted by default unless `--decrypt` and `--include-secrets` are passed.

## Testing

Tests use **moto** to mock SSM. All tests run against an in-process mock — no AWS credentials needed.

```
# Run all tests
.venv/bin/pytest

# Run a specific test module
.venv/bin/pytest tests/test_cli.py -v

# Run with coverage
.venv/bin/pytest --cov=ssmtree --cov-report=term-missing
```

## Code Style

- **Ruff**: line length 100, Python 3.11 target, rules `E F I UP`
- **Black**: default settings (used for formatting)
- **mypy**: strict mode, `ignore_missing_imports = true`
