# Publishing to PyPI

## Prerequisites

- A [PyPI account](https://pypi.org/account/register/)
- A PyPI API token (create one at https://pypi.org/manage/account/token/)
- Python virtual environment set up for this project

## Steps

### 1. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 2. Install build tools

```bash
pip install build twine
```

### 3. Build the distribution

```bash
python -m build
```

This creates two files in the `dist/` directory:
- `ssmtree-<version>.tar.gz` (source distribution)
- `ssmtree-<version>-py3-none-any.whl` (wheel)

### 4. Upload to PyPI

```bash
twine upload dist/* -u __token__ -p pypi-YOUR_API_TOKEN_HERE
```

- Username is literally `__token__`
- Password is your PyPI API token (starts with `pypi-`)

## Updating the version

Before publishing a new release, update the `version` field in `pyproject.toml`, then clean and rebuild:

```bash
rm -rf dist/
python -m build
twine upload dist/* -u __token__ -p pypi-YOUR_API_TOKEN_HERE
```

## Testing with TestPyPI (optional)

To test the upload before publishing to the real PyPI:

```bash
twine upload --repository testpypi dist/* -u __token__ -p pypi-YOUR_TEST_TOKEN
```

Then install from TestPyPI to verify:

```bash
pip install --index-url https://test.pypi.org/simple/ ssmtree
```
