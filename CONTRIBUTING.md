# Contributing to ssmtree

Thank you for your interest in contributing to ssmtree! This guide will help you get started.

## Getting Started

### Prerequisites

- **Python 3.11+**
- **AWS credentials** (only needed for integration testing; unit tests use moto mocking)

### Dev Setup

```bash
git clone https://github.com/Specter099/ssmtree.git
cd ssmtree
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

All tests use [moto](https://github.com/getmoto/moto) to mock AWS services, so no real AWS credentials are required for the test suite.

```bash
pytest
```

To run tests with verbose output:

```bash
pytest -v
```

## Code Style

We use the following tools to maintain code quality:

| Tool | Purpose | Command |
|------|---------|---------|
| **Ruff** | Linting | `ruff check src tests` |
| **Black** | Formatting | `black src tests` |
| **mypy** | Type checking | `mypy src` |

Line length is set to **100** characters.

Run all checks before submitting a PR:

```bash
ruff check src tests
black --check src tests
mypy src
```

## Making Changes

1. **Branch from `main`** — Always create a new branch for your work.
2. **Use descriptive branch names** — e.g., `feature/add-output-format`, `fix/unicode-path-handling`.
3. **Keep commits focused** — Each commit should represent a single logical change.

## Pull Request Process

1. Fill out the PR template when opening your pull request.
2. Ensure all CI checks pass (linting, tests, type checking).
3. Request a review from a maintainer.
4. Address any review feedback promptly.

## Reporting Bugs

Found a bug? Please open an issue using the [bug report template](https://github.com/Specter099/ssmtree/issues/new?template=bug_report.md). Include as much detail as possible to help us reproduce and fix the issue.

## Requesting Features

Have an idea for a new feature? Open an issue using the [feature request template](https://github.com/Specter099/ssmtree/issues/new?template=feature_request.md). We welcome suggestions that align with ssmtree's goal of making SSM Parameter Store easier to navigate.
