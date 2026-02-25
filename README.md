# ssmtree

[![CI](https://github.com/Specter099/ssmtree/actions/workflows/ci.yml/badge.svg)](https://github.com/Specter099/ssmtree/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Render AWS SSM Parameter Store as a colorized terminal tree. Browse, diff, and copy parameters across namespaces.

## Features

- **Tree view** — Visualize SSM parameters as a rich, colorized tree in your terminal
- **Diff** — Compare parameters between two namespaces side by side
- **Copy** — Copy parameters from one namespace to another with dry-run support
- **Glob filtering** — Filter parameters with glob patterns to focus on what matters
- **JSON output** — Export parameter trees as JSON for scripting and automation
- **Decrypt support** — Decrypt SecureString parameters inline with optional KMS key re-encryption

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Basic tree view
ssmtree /app/prod

# With decryption
ssmtree --decrypt /app/prod

# Filter parameters with a glob pattern
ssmtree --filter "*db*" /app

# JSON output
ssmtree --output json /app/prod
```

## Commands

### diff

Compare parameters between two namespaces:

```bash
ssmtree diff /app/prod /app/staging
```

### copy

Copy parameters from one namespace to another:

```bash
# Preview what would be copied
ssmtree copy --dry-run /app/prod /app/staging

# Copy with overwrite, decryption, and re-encryption under a new KMS key
ssmtree copy --overwrite --decrypt --kms-key-id alias/my-key /app/prod /app/staging
```

## Development

```bash
git clone https://github.com/Specter099/ssmtree.git
cd ssmtree
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE)
