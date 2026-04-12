# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ssmtree is a Python CLI tool for browsing, diffing, copying, and writing AWS SSM Parameter Store parameters, rendered as a colorized terminal tree. Built with Click, boto3, and Rich.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Common Commands

```
# Browse parameters as a tree
.venv/bin/ssmtree /app/prod
.venv/bin/ssmtree --decrypt /app/prod
.venv/bin/ssmtree --hide-values /app/prod
.venv/bin/ssmtree --filter "*db*" /app
.venv/bin/ssmtree --output json /app/prod

# Diff two namespaces
.venv/bin/ssmtree diff /app/prod /app/staging

# Copy parameters between namespaces
.venv/bin/ssmtree copy --dry-run /app/prod /app/staging
.venv/bin/ssmtree copy --yes --overwrite /app/prod /app/staging

# Write a single parameter
.venv/bin/ssmtree put /app/prod/db/host my-host
.venv/bin/ssmtree put --secure --stdin /app/prod/db/password

# Run tests
.venv/bin/pytest

# Lint
.venv/bin/ruff check .

# Type check
.venv/bin/mypy src/
```

## Directory Structure

```
src/ssmtree/
  cli.py          # Click CLI entry point (tree, diff, copy, put commands)
  fetcher.py      # Fetches parameters from SSM via boto3
  tree.py         # Builds tree data structure from flat parameter list
  differ.py       # Diffs two parameter namespaces
  copier.py       # Copies parameters between namespaces
  putter.py       # Writes a single parameter to SSM
  formatters.py   # Rich tree, diff table, and copy plan renderers
  models.py       # Data models (Parameter, TreeNode)
tests/
  conftest.py     # Shared fixtures
  fixtures/       # Test data (parameters.json)
  test_cli.py     # CLI integration tests
  test_fetcher.py # Fetcher tests (uses moto)
  test_tree.py    # Tree builder tests
  test_differ.py  # Differ tests
  test_copier.py  # Copier tests
  test_putter.py  # Putter tests
  test_formatters.py # Formatter tests
  test_models.py  # Model tests
```

## Architecture

Click group CLI (`ssmtree.cli:main`, installed as `ssmtree`) with subcommands: `diff`, `copy`, `put`, and an implicit default tree view via a positional PATH argument. Source code uses the src layout (`src/ssmtree/`).

The default command (no subcommand) renders the parameter tree. The custom `_DefaultPathGroup` Click group class handles routing between subcommand mode and positional PATH mode.

## Testing

Tests use `pytest` with `moto[ssm]` for mocking AWS SSM.

```
.venv/bin/pytest                     # Run all tests
.venv/bin/pytest tests/test_cli.py   # Run specific test file
.venv/bin/pytest -x                  # Stop on first failure
```

## Code Style

Ruff is configured with line-length 100, targeting Python 3.11. Rules: E, F, I, UP. Mypy is configured in strict mode.
