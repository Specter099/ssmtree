#!/usr/bin/env python3
"""Prepare a new ssmtree release.

Automates the mechanical, error-prone parts of cutting a release:

1. Bumps the version in **both** ``pyproject.toml`` and
   ``src/ssmtree/__init__.py`` (these must stay in sync).
2. Rolls the ``CHANGELOG.md`` ``[Unreleased]`` section into a dated
   ``[X.Y.Z]`` section and adds the release-tag link reference.
3. Runs the quality gates + a real build (``ruff``, ``mypy``, ``pytest``,
   ``python -m build``, ``twine check``).
4. Commits the result on a ``release/vX.Y.Z`` branch.

It stops short of the irreversible step: publishing the GitHub Release
(which triggers ``.github/workflows/publish.yml`` and the OIDC upload to
PyPI). That final click stays with a human — the script prints the exact
next steps.

Examples
--------
    python scripts/release.py 0.5.0          # explicit version
    python scripts/release.py --bump minor   # 0.4.0 -> 0.5.0
    python scripts/release.py --bump patch --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT_PY = REPO_ROOT / "src" / "ssmtree" / "__init__.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"  {msg}")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command from the repo root, streaming output."""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    if check and result.returncode != 0:
        fail(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def tool(name: str) -> str:
    """Prefer the project's virtualenv binary, else fall back to PATH."""
    candidate = REPO_ROOT / ".venv" / "bin" / name
    return str(candidate) if candidate.exists() else name


def current_version() -> str:
    m = re.search(r'^version = "([^"]+)"', PYPROJECT.read_text(), re.MULTILINE)
    if not m:
        fail(f"could not find a top-level version in {PYPROJECT}")
    return m.group(1)  # type: ignore[union-attr]


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def repo_slug() -> str:
    """Derive ``owner/repo`` from an existing CHANGELOG link, else git remote."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/releases", CHANGELOG.read_text())
    if m:
        return m.group(1)
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote)
    return m.group(1) if m else "OWNER/REPO"


# --------------------------------------------------------------------------- #
# File edits (pure: return new text; caller decides whether to write)
# --------------------------------------------------------------------------- #
def bump_version_text(text: str, pattern: str, new_version: str) -> str:
    new_text, n = re.subn(pattern, rf'\g<1>{new_version}"', text, count=1, flags=re.MULTILINE)
    if n != 1:
        fail(f"expected exactly one match for {pattern!r}, found {n}")
    return new_text


def roll_changelog(text: str, new_version: str, date: str, slug: str) -> str:
    if "## [Unreleased]" not in text:
        fail("CHANGELOG.md has no '## [Unreleased]' section")

    # Warn (don't block) if there is nothing under [Unreleased] to release.
    unreleased = re.search(
        r"## \[Unreleased\]\s*(.*?)(?=\n## \[)", text, re.DOTALL
    )
    if unreleased and not unreleased.group(1).strip():
        print("warning: the [Unreleased] section is empty — releasing with no notes")

    # Insert the new dated section directly under the (now empty) Unreleased heading.
    text, n = re.subn(
        r"## \[Unreleased\]\n",
        f"## [Unreleased]\n\n## [{new_version}] - {date}\n",
        text,
        count=1,
    )
    if n != 1:
        fail("failed to insert new version heading into CHANGELOG.md")

    # Add the link reference above the first existing one (newest on top).
    link = f"[{new_version}]: https://github.com/{slug}/releases/tag/v{new_version}\n"
    m = re.search(r"^\[\d+\.\d+\.\d+\]: ", text, re.MULTILINE)
    if m:
        text = text[: m.start()] + link + text[m.start() :]
    else:
        text = text.rstrip() + "\n\n" + link
    return text


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare an ssmtree release (bump, changelog, verify, commit).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="explicit new version, e.g. 0.5.0")
    group.add_argument("--bump", choices=["major", "minor", "patch"], help="bump a version part")
    parser.add_argument("--dry-run", action="store_true", help="show changes; write nothing")
    parser.add_argument("--no-verify", action="store_true", help="skip ruff/mypy/pytest/build")
    parser.add_argument(
        "--no-branch", action="store_true", help="commit on the current branch (no release branch)"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    if not PYPROJECT.exists():
        fail("run this from the ssmtree repo (pyproject.toml not found)")

    cur = current_version()
    new = args.version if args.version else bump(cur, args.bump)
    if not SEMVER_RE.match(new):
        fail(f"invalid version {new!r} (expected MAJOR.MINOR.PATCH)")
    if new == cur:
        fail(f"new version {new} is the same as the current version")

    date = datetime.date.today().isoformat()
    slug = repo_slug()
    tag = f"v{new}"

    print(f"\nRelease {cur} -> {new}  ({date})\n")

    # Compute all edits up-front so a failure leaves nothing half-written.
    edits = {
        PYPROJECT: bump_version_text(
            PYPROJECT.read_text(), r'^(version = ")[^"]+"', new
        ),
        INIT_PY: bump_version_text(
            INIT_PY.read_text(), r'^(__version__ = ")[^"]+"', new
        ),
        CHANGELOG: roll_changelog(CHANGELOG.read_text(), new, date, slug),
    }

    for path in edits:
        info(f"update {path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        print("\n[dry-run] no files written, no git actions taken.")
        print(f"[dry-run] would create tag {tag} and commit on "
              f"{'current branch' if args.no_branch else f'release/{tag}'}.")
        return

    # Refuse to run on a dirty tree — the only changes in the commit should be ours.
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        fail("working tree is not clean — commit or stash changes first:\n" + dirty)

    if not args.yes:
        reply = input(f"\nProceed with release {new}? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted.")
            return

    for path, text in edits.items():
        path.write_text(text)
        info(f"wrote {path.relative_to(REPO_ROOT)}")

    if not args.no_verify:
        print("\nRunning verification...")
        run([tool("ruff"), "check", "src", "tests"])
        run([tool("mypy"), "src"])
        run([tool("pytest"), "-q"])
        run([sys.executable, "-m", "build"])
        run([tool("twine"), "check", "dist/*"]) if (REPO_ROOT / "dist").exists() else None

    # Commit (optionally on a dedicated release branch).
    if not args.no_branch:
        run(["git", "checkout", "-b", f"release/{tag}"])
    run(["git", "add", str(PYPROJECT), str(INIT_PY), str(CHANGELOG)])
    run(["git", "commit", "-m", f"chore: release {new}"])

    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()

    print(f"""
Release {new} prepared and committed on branch '{branch}'.

Next steps (the publish is a human action — it uploads to PyPI):
  1. git push -u origin {branch}
  2. Open a PR into main and merge it once CI is green.
  3. Create a GitHub Release for tag {tag} targeting main:
       gh release create {tag} --target main --title "{tag}" \\
         --notes "$(sed -n '/## \\[{new}\\]/,/## \\[/p' CHANGELOG.md | sed '$d')"
     (or use the GitHub UI: Releases -> Draft a new release -> tag {tag})
  4. Publishing the Release triggers publish.yml, which builds and uploads
     {new} to PyPI via OIDC trusted publishing. Watch the run under Actions.
""")


if __name__ == "__main__":
    main()
