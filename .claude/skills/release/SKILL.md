---
name: release
description: Cut a new ssmtree release to PyPI. Use when the user asks to release, publish, ship, or bump the version of ssmtree (e.g. "release 0.5.0", "publish a new version", "do a patch release"). Wraps scripts/release.py (version bump + changelog + verify + commit) and drives the PR, GitHub Release, and OIDC publish through to confirmation on PyPI.
---

# Release ssmtree

Cut a new release. The mechanical prep is automated by `scripts/release.py`;
the publish itself happens when a GitHub Release is created (that triggers
`.github/workflows/publish.yml`, which uploads to PyPI via OIDC trusted
publishing — no token).

## Steps

1. **Pick the version.** If the user gave one, use it. Otherwise infer the
   bump from the `[Unreleased]` changelog entries (new features → `--bump
   minor`, fixes only → `--bump patch`, breaking → `--bump major`) and confirm
   with the user.

2. **Preview**, then run the prep script from the repo root:
   ```bash
   python scripts/release.py <version> --dry-run   # show what changes
   python scripts/release.py <version> --yes       # bump + changelog + verify + commit
   ```
   The script bumps the version in `pyproject.toml` **and**
   `src/ssmtree/__init__.py`, rolls `CHANGELOG.md` `[Unreleased]` into a dated
   section, runs ruff/mypy/pytest/build/twine, and commits on a
   `release/vX.Y.Z` branch. If verification fails, fix the failure before
   continuing — do not release red.

3. **Push and open a PR** into `main`; wait for CI to go green, then merge.

4. **Create the GitHub Release** for tag `vX.Y.Z` targeting `main`. There is no
   MCP tool for this and tag pushes may be blocked in the sandbox, so either
   run `gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes "<the
   CHANGELOG section>"`, or ask the user to click **Releases → Draft a new
   release** and publish. Publishing is the irreversible step — confirm the
   user wants to ship before creating the Release.

5. **Watch `publish.yml`** (Actions → Publish). Confirm all jobs pass and that
   the new version is live at `https://pypi.org/pypi/ssmtree/<version>/json`.
   If the publish job fails on the OIDC exchange, the PyPI trusted publisher
   isn't configured — see `PUBLISHING.md` (owner `Specter099`, repo `ssmtree`,
   workflow `publish.yml`, environment `pypi`), or fall back to `twine upload`.
