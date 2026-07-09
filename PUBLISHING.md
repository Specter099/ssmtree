# Publishing to PyPI

`ssmtree` publishes to PyPI automatically via **Trusted Publishing (OIDC)** when a
GitHub Release is published. No API token is stored or needed.

## Release process (recommended)

1. **Bump the version** in both places (they must match):
   - `version` in `pyproject.toml`
   - `__version__` in `src/ssmtree/__init__.py`

2. **Update `CHANGELOG.md`**: move the `[Unreleased]` entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading and add a link reference at the bottom.

3. **Merge to `main`** via a pull request (CI must pass).

4. **Create a GitHub Release** with a tag `vX.Y.Z` (matching the version).
   Publishing the release triggers `.github/workflows/publish.yml`, which:
   - runs the test suite (Python 3.11 and 3.12),
   - builds the sdist + wheel,
   - publishes to PyPI via the `pypa/gh-action-pypi-publish` OIDC action
     (GitHub environment `pypi`).

### One-time PyPI setup

Trusted Publishing must be configured once on the PyPI project side:
PyPI → project **ssmtree** → *Settings → Publishing → Add a new publisher*:

- Owner: `Specter099`
- Repository: `ssmtree`
- Workflow: `publish.yml`
- Environment: `pypi`

## Testing a build locally (before releasing)

```bash
source .venv/bin/activate
pip install build twine
rm -rf dist/
python -m build          # writes dist/ssmtree-<version>.tar.gz and .whl
twine check dist/*       # validate metadata / long description
pip install dist/ssmtree-<version>-py3-none-any.whl   # smoke-test in a clean venv
ssmtree --version
```

## Manual upload (fallback only)

Use only if OIDC publishing is unavailable. Requires a PyPI API token
(`pypi-…`) and skips the CI gates:

```bash
python -m build
twine upload dist/* -u __token__ -p pypi-YOUR_API_TOKEN_HERE
```

### TestPyPI (optional dry run)

```bash
twine upload --repository testpypi dist/* -u __token__ -p pypi-YOUR_TEST_TOKEN
pip install --index-url https://test.pypi.org/simple/ ssmtree
```
