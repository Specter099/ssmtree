# Security & Operational Review

**Project:** ssmtree (PyPI: `ssmtree`, v0.3.2)
**Reviewed at:** commit `5a1ec14`, 2026-07-09
**Scope:** application source (`src/ssmtree/`), test suite, packaging (`pyproject.toml`), CI/CD workflows (`.github/workflows/`), and repository governance files.
**Method:** three parallel review passes — source-code security (secret handling, injection, AWS API usage), supply-chain/operational posture (CI, packaging, publishing), and runtime robustness (error handling, safeguards, test coverage). All high/medium findings were verified against the code at the anchors cited below.

---

## Summary

ssmtree has a strong security baseline for a CLI of its kind: SecureString values are redacted by default (with tests asserting it), write operations default to `Overwrite=False` behind confirmation prompts, paths are validated against a strict regex on every command, PyPI publishing uses OIDC trusted publishing, CI actions are SHA-pinned, and there is no shell/exec/temp-file/hard-coded-credential exposure anywhere in the codebase.

The findings below are therefore mostly about closing gaps in an otherwise consistent design: the `copy` subcommand missed three protections the other commands have (decrypt-awareness, error sanitization, failure exit codes), and the release/backup workflows are pinned less strictly than CI.

| # | Severity | Finding | Anchor |
|---|----------|---------|--------|
| 1 | High | `copy` writes KMS ciphertext as SecureString value when `--decrypt` omitted | `copier.py:85-92`, `cli.py:329` |
| 2 | High | `copy` error messages not sanitized (ARNs / account IDs leak) | `copier.py:97-99`, `cli.py:376-377` |
| 3 | High | Uncaught traceback on bad `--profile` / unresolved region | `fetcher.py:35-38,61`, `cli.py:354,483` |
| 4 | High | Publish workflow uses mutable action refs (tags/branch, not SHAs) | `.github/workflows/publish.yml` |
| 5 | High | Backup workflow: `secrets: inherit` into reusable workflow pinned `@main` | `.github/workflows/backup.yml` |
| 6 | Medium | `copy` exits 0 on partial/total write failure | `cli.py:374-377` |
| 7 | Medium | No `permissions:` block in `ci.yml` | `.github/workflows/ci.yml` |
| 8 | Medium | No lockfile; floor-only dependency bounds; unpinned dev tools | `pyproject.toml` |
| 9 | Medium | mypy (strict) never run in CI; coverage not gated | `.github/workflows/ci.yml` |
| 10 | Medium | `--include-secrets` warning printed to stdout, corrupting JSON | `cli.py:170-184,244-247` |
| 11+ | Low | Hygiene items (stale docs, metadata, dead code, etc.) | see below |

---

## High-priority findings

### 1. `copy` silently corrupts SecureStrings when `--decrypt` is omitted

`copy_cmd` fetches source parameters with `decrypt=decrypt` (`cli.py:329`). When `--decrypt` is not passed, the SSM API returns SecureString `Value` fields as the raw KMS ciphertext blob. `copy_namespace` then writes that blob verbatim as the destination value (`copier.py:85-92`), which AWS re-encrypts — the destination secret is unusable garbage, and nothing warns the user. The dry-run plan (`formatters.py:154-181`) shows only paths and types, so it gives no signal either.

**Remediation:** in `copy_cmd`, when the fetched source set contains any `SecureString` and `--decrypt` is not set, refuse with a clear error (preferred) or require an explicit override flag. Additionally, mark SecureStrings in `render_copy_plan` output. Add tests for both the refusal and the decrypted-copy happy path.

### 2. `copy` error messages bypass sanitization

`fetcher.py:25-29` and `putter.py:22-28` both strip ARNs and 12-digit account IDs from AWS error messages before display (putter also strips the parameter value itself). The copy path does neither: `copier.py:97-99` captures the raw `ClientError` message and `cli.py:376-377` prints it verbatim. AWS `AccessDenied` and KMS errors routinely embed the caller ARN and account ID.

**Remediation:** extract a single shared `sanitize_error()` (e.g. in a small `_errors.py` or on `fetcher`) and route fetcher, putter, and copier through it. Add a copier test asserting account IDs/ARNs are scrubbed from `failed` entries.

### 3. Uncaught traceback on bad `--profile` or unresolved region

`make_client` (`fetcher.py:35-38`) raises `botocore.exceptions.ProfileNotFound` / `NoRegionError` at client-construction time, and every call site sits outside the surrounding `try` blocks (`fetcher.py:61`, `cli.py:354`, `cli.py:483`). A typo'd profile or missing region — the two most common user misconfigurations — dumps a raw Python traceback instead of a clean error.

**Remediation:** catch `ProfileNotFound`/`NoRegionError`/`BotoCoreError` around client creation (either inside `make_client` or at the call sites) and surface via `_abort()`. Add CLI tests for an invalid profile and a missing region.

### 4. Publish workflow uses mutable action references

`ci.yml` correctly pins all actions to full commit SHAs, but `publish.yml` — the workflow that ships to PyPI — uses floating refs: `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@v7`, `actions/download-artifact@v8`, and `pypa/gh-action-pypi-publish@release/v1` (a moving branch). A compromised or re-pointed tag on the release path is the highest-impact supply-chain scenario for a published package. (`claude.yml` has the same tag-pinning pattern.)

**Remediation:** SHA-pin every action in `publish.yml` and `claude.yml` with a version comment, matching the `ci.yml` convention. Dependabot's `github-actions` ecosystem already keeps SHA pins fresh.

### 5. Backup workflow inherits all secrets into a mutable ref

`backup.yml` calls `Specter099/.github/.github/workflows/repo-backup.yml@main` with `secrets: inherit`. Every repo/org secret flows into whatever `@main` points to at run time.

**Remediation:** pin the reusable workflow to a commit SHA (or at least a tag), and replace `secrets: inherit` with an explicit pass-through of only the secrets the backup needs.

---

## Medium-priority findings

### 6. `copy` exits 0 on write failures

`cli.py:374-377` prints `Failed N parameter(s)` but never exits nonzero; `test_cli.py:271-283` codifies exit code 0 on a run with failures. Scripts and CI cannot detect a partially failed copy. Related: `except CopyError` at `cli.py:366` is dead code — `copy_namespace` never raises it.

**Remediation:** `sys.exit(1)` when `failed` is non-empty; update the test contract. Either use `CopyError` for whole-operation failures or remove the dead handler.

### 7. `ci.yml` has no `permissions:` block

The workflow inherits the default `GITHUB_TOKEN` scope. **Remediation:** add top-level `permissions: contents: read`.

### 8. No lockfile; floor-only dependency bounds

Runtime deps are floors only (`click>=8.1`, `rich>=13.0`, `boto3>=1.26`); most dev extras (`pytest-cov`, `black`, `ruff`, `mypy`, `boto3-stubs`) are fully unbounded; CI installs `pip-audit` unpinned. Fresh installs and CI runs are non-reproducible, and a new major of any dependency lands unvetted.

**Remediation:** generate a lock/constraints file (`uv lock` or pip-tools) and use it in CI (`pip install -c constraints.txt`); pin `pip-audit`. Keep floors in `pyproject.toml` for library-style install flexibility. Also raise `moto[ssm]>=4` to `>=5` — the tests use the moto 5 `mock_aws` API.

### 9. mypy strict configured but never enforced; coverage not gated

CI runs ruff and pytest-with-coverage but no mypy, despite `strict = true` in `pyproject.toml`; coverage is reported but has no threshold.

**Remediation:** add `mypy src` as a CI step and `--cov-fail-under=<current%>` to the pytest invocation.

### 10. `--include-secrets` warning corrupts JSON on stdout

The "Secret values will be included in output" warning is printed via the stdout `console` immediately before the JSON payload (`cli.py:170-184`, `cli.py:244-247`), so `ssmtree --output json --include-secrets /x | jq` breaks. The equivalent `put` warning correctly uses `err_console` (`cli.py:464`).

**Remediation:** route both warnings through `err_console`.

---

## Low-priority / hygiene findings

- **Stale governance docs:** `CHANGELOG.md` stops at 0.1.0 and `SECURITY.md`'s supported-versions table lists only 0.1.x, while 0.3.2 is shipping. Update both; add changelog maintenance to the `PUBLISHING.md` checklist.
- **CVE suppressions untracked:** CI ignores `CVE-2026-4539` and `CVE-2026-3219` in pip-audit with no comment. Add an inline comment with rationale and a removal condition, and re-check on dependency bumps.
- **Thin PyPI metadata:** no `classifiers`, `keywords`, `authors`, or `[project.urls]` in `pyproject.toml`. The SPDX-string `license = "MIT"` form needs a newer setuptools than the pinned `>=61` floor guarantees — raise the build requirement or use the table form.
- **Redaction gated on two different flags:** human-readable output reveals secrets with `--decrypt`; JSON requires `--include-secrets`. Defensible, but document the distinction in `README.md`/`--help`.
- **Undecrypted SecureString diff always reports "changed":** KMS ciphertext is non-deterministic, so identical secrets diff as changed (`differ.py:48-52`). Document, or annotate SecureString rows as "not comparable without --decrypt".
- **Rich markup escaping relies on AWS's charset:** diff/copy-plan table cells and titles pass bare strings to Rich `Table` (`formatters.py:121,133,140,149,170,179`; also `cli.py:505`), safe only because SSM names cannot contain `[`/`]`. Escape locally so the invariant doesn't depend on external input constraints.
- **`BotoCoreError` detail discarded in copy:** `copier.py:100-101` collapses all such errors to `"AWS API error"` — safe but undiagnosable. Include the exception class name after sanitization.
- **No `--endpoint-url` option:** localstack/VPC-endpoint use requires env-var workarounds.
- **No pre-commit config** despite ruff/black/mypy being dev deps.
- **Bus factor 1:** `CODEOWNERS` is `* @Specter099`; no in-repo evidence of branch protection. Confirm required status checks on `main` in repo settings.

---

## Positives (keep doing these)

- Redaction by default, with explicit tests asserting redacted output and absent ciphertext (`test_formatters.py:79-86,157-171`; `test_cli.py:74-106,205-214`).
- `Overwrite=False` defaults on both write paths, enforced server-side (no check-then-write race); confirmation prompts on copy and on `put --overwrite`; `--overwrite --stdin` correctly requires `--yes`.
- `--stdin` for secret input plus a stderr warning when a SecureString is passed as a CLI argument.
- Strict path validation (`^(?:/[a-zA-Z0-9_.-]+)+$`) applied on every command.
- `put` error sanitizer also strips the parameter value itself, using `.replace()` (regex-metacharacter safe, tested).
- Adaptive retry config (`max_attempts: 5, mode: adaptive`) applied to every client via a single factory; correct `NextToken` pagination.
- OIDC trusted publishing (no PyPI API token), environment-gated, with test+build gates before publish.
- SHA-pinned actions in `ci.yml`; dependabot active for pip and github-actions; moto-only tests with dummy credentials.
- No `eval`/`exec`/`subprocess`/shell usage, no temp files, no hard-coded credentials, no telemetry.

---

## Remediation roadmap

**Phase 1 — close the high-severity gaps (small, independent changes):**
1. Block (or gate) SecureString copy without `--decrypt`; flag SecureStrings in the copy plan. *(Finding 1)*
2. Shared `sanitize_error()` used by fetcher, putter, and copier; test copier scrubbing. *(2)*
3. Wrap `make_client` failures → clean `_abort` message; tests for bad profile/region. *(3)*
4. SHA-pin actions in `publish.yml` and `claude.yml`. *(4)*
5. Pin `backup.yml`'s reusable workflow to a SHA; replace `secrets: inherit` with explicit secrets. *(5)*

**Phase 2 — operational correctness:**
6. Nonzero exit on copy failures; resolve dead `CopyError` handler. *(6)*
7. `permissions: contents: read` in `ci.yml`; mypy step; coverage gate; pin `pip-audit`. *(7, 9)*
8. Add a lockfile/constraints used by CI; bump moto floor to `>=5`. *(8)*
9. Move `--include-secrets` warnings to stderr. *(10)*

**Phase 3 — hygiene:**
10. Refresh `CHANGELOG.md` and `SECURITY.md`; annotate CVE suppressions; enrich PyPI metadata; document the `--decrypt` vs `--include-secrets` gates and the SecureString-diff caveat; local Rich escaping; pre-commit config; consider `--endpoint-url`.

Phases 1–2 are all small, test-covered changes; nothing requires an architectural refactor.
