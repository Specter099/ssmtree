# ssmtree

[![CI](https://github.com/Specter099/ssmtree/actions/workflows/ci.yml/badge.svg)](https://github.com/Specter099/ssmtree/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ssmtree)](https://pypi.org/project/ssmtree/)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Render AWS SSM Parameter Store as a colorized terminal tree. Browse, diff, and copy parameters across namespaces.

## Features

- **Tree view** — Visualize SSM parameters as a rich, colorized tree in your terminal
- **Diff** — Compare parameters between two namespaces side by side
- **Copy** — Copy parameters from one namespace to another with dry-run support
- **Glob filtering** — Filter parameters with glob patterns to focus on what matters
- **JSON output** — Export parameter trees or diffs as JSON for scripting and automation
- **Decrypt support** — Decrypt SecureString parameters inline with optional KMS key re-encryption
- **SecureString safety** — SecureString values shown as `[redacted]` by default; use `--decrypt` to reveal them
- **Leaf parameter support** — Query a single leaf parameter directly (e.g. `ssmtree /app/db/password`)

## Installation

```bash
pip install ssmtree
```

For development:

```bash
git clone https://github.com/Specter099/ssmtree.git
cd ssmtree
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```bash
# Browse all parameters under a prefix
ssmtree /app/prod

# Query a single leaf parameter
ssmtree /app/prod/db/password

# Decrypt SecureString values (shown as [redacted] by default)
ssmtree --decrypt /app/prod

# Hide all values entirely
ssmtree --hide-values /app/prod

# Filter with a glob pattern
ssmtree --filter "*db*" /app

# JSON output (SecureStrings redacted by default)
ssmtree --output json /app/prod

# JSON output with SecureString values included
ssmtree --decrypt --output json --include-secrets /app/prod
```

## Commands

### diff

Compare parameters between two namespaces:

```bash
# Table diff (default)
ssmtree diff /app/prod /app/staging

# With decryption
ssmtree diff --decrypt /app/prod /app/staging

# JSON diff output
ssmtree diff --output json /app/prod /app/staging

# JSON diff with SecureString values included
ssmtree diff --decrypt --output json --include-secrets /app/prod /app/staging
```

### copy

Copy parameters from one namespace to another:

```bash
# Preview what would be copied
ssmtree copy --dry-run /app/prod /app/staging

# Copy (prompts for confirmation)
ssmtree copy /app/prod /app/staging

# Copy with overwrite, skip confirmation
ssmtree copy --yes --overwrite /app/prod /app/staging

# Copy with decryption and re-encryption under a new KMS key
ssmtree copy --decrypt --kms-key-id alias/my-key /app/prod /app/staging
```

## Options

| Option | Commands | Description |
|--------|----------|-------------|
| `--decrypt` / `-d` | all | Decrypt SecureString values |
| `--profile` | all | AWS named profile to use |
| `--region` | all | AWS region override |
| `--show-values` / `--hide-values` | `main`, `diff` | Show or hide parameter values (default: show) |
| `--filter PATTERN` / `-f` | `main` | Glob filter on parameter paths |
| `--output` | `main`, `diff` | Output format: `tree`/`table` (default) or `json` |
| `--include-secrets` | `main`, `diff` | Include SecureString values in JSON output |
| `--overwrite` / `--no-overwrite` | `copy` | Overwrite existing destination parameters |
| `--dry-run` | `copy` | Show what would be copied without writing |
| `--kms-key-id` | `copy` | KMS key for SecureString parameters at destination |
| `--yes` / `-y` | `copy` | Skip confirmation prompt |

## Development

```bash
pytest          # run tests
ruff check .    # lint
```

## License

MIT — see [LICENSE](LICENSE)
