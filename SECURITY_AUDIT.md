# Security Audit Report — ssmtree

**Date:** 2026-02-25
**Scope:** Full codebase review (src/, tests/, CI/CD, dependencies)
**Auditor:** Automated security review
**Version audited:** 0.1.0

---

## Executive Summary

ssmtree is a well-structured CLI tool with a small attack surface. It delegates
authentication and encryption to AWS (boto3/KMS) and does not implement custom
cryptography. The primary security concerns center around **secret exposure in
output channels**, **lack of confirmation on destructive operations**, and
**non-atomic copy behavior**. The codebase has no injection vulnerabilities, no
file-write operations in production code, and clean dependency hygiene.

**Finding counts by severity:**

| Severity | Count |
|----------|-------|
| High     | 3     |
| Medium   | 5     |
| Low      | 5     |

---

## HIGH Severity Findings

### H1 — Decrypted SecureString Values Dumped to stdout in JSON Output

**Location:** `src/ssmtree/cli.py:131-142` (main command), `src/ssmtree/cli.py:184-198` (diff command)

**Description:**
When `--output json` is combined with `--decrypt`, all parameter values —
including decrypted `SecureString` secrets — are serialized as plain JSON to
stdout. This output can be trivially captured by:

- Shell pipelines (`ssmtree --decrypt --output json /prod > file.json`)
- Terminal scrollback buffers and screen recordings
- CI/CD job logs if the tool is used in automation
- Process substitution visible in `/proc/<pid>/fd/`

The diff JSON output similarly exposes `old_value` and `new_value` for changed
parameters.

**Risk:** Credential leakage through logging, shell history, or automation
artifacts.

**Recommendation:**
1. Redact `SecureString` values in JSON output by default (emit
   `"***REDACTED***"`), and require an explicit `--include-secrets` flag to
   include them.
2. Emit a stderr warning when `--decrypt` and `--output json` are combined:
   `"WARNING: Secret values will be included in output."`
3. Consider writing sensitive JSON output to a file descriptor rather than
   stdout, or support `--output-file` with restricted file permissions (0600).

---

### H2 — No Confirmation Prompt for Destructive Copy Operations

**Location:** `src/ssmtree/cli.py:260-273`

**Description:**
The `copy` command writes parameters to the destination namespace immediately
without any interactive confirmation. A typo in the destination path (e.g.,
`/app/prod` instead of `/app/staging`) could overwrite production parameters.
The `--overwrite` flag compounds this: with it enabled, existing production
values are silently replaced.

The only safeguard is `--dry-run`, but it must be explicitly supplied — it is
not the default behavior.

**Risk:** Accidental or unauthorized modification of production SSM parameters.

**Recommendation:**
1. Add an interactive confirmation prompt before writing (e.g.,
   `"Copy 15 parameters to /app/prod? [y/N]"`), suppressible with `--yes`/`-y`.
2. When `--overwrite` is used, display a bold warning indicating which existing
   parameters will be replaced.
3. Consider making `--dry-run` the default, requiring `--execute` to actually
   write.

---

### H3 — Copy Operation Is Non-Atomic With No Rollback

**Location:** `src/ssmtree/copier.py:74-88`

**Description:**
Parameters are written one-by-one in a loop. If the process is interrupted or
an API error occurs mid-copy (e.g., on parameter 5 of 10), the destination
namespace is left in a partially-written, inconsistent state. There is no
rollback mechanism, no transaction log, and no indication of which parameters
were successfully written before the failure.

**Risk:** Inconsistent configuration state in the destination namespace, which
could cause application failures if the destination is actively used.

**Recommendation:**
1. Wrap the copy loop in a try/except that catches per-parameter failures and
   reports a summary (e.g., "8/10 succeeded, 2 failed: [paths]").
2. Log all successfully written paths so the operator can diagnose and recover.
3. Consider adding a `--rollback-on-error` flag that deletes any parameters
   written during a failed copy attempt.
4. At minimum, print the list of successfully written parameters before raising
   the error.

---

## MEDIUM Severity Findings

### M1 — Error Messages May Leak Internal AWS Details

**Location:** `src/ssmtree/fetcher.py:75`, `src/ssmtree/cli.py:22-24`

**Description:**
The `FetchError` wraps the full AWS exception message, which can contain AWS
account IDs, resource ARNs, IAM role names, and internal service details. This
is printed directly to the console via `_abort()`.

```python
raise FetchError(f"Failed to fetch parameters from SSM: {exc}") from exc
```

**Risk:** Information disclosure of internal AWS infrastructure details.

**Recommendation:**
1. Sanitize error messages before display — strip ARNs and account IDs, or
   provide a generic user-facing message while logging the full exception for
   debugging with `--verbose`.
2. Add a `--debug` flag that enables full exception output; keep default output
   minimal.

---

### M2 — `--show-values` Is the Default

**Location:** `src/ssmtree/cli.py:82-85`

**Description:**
Parameter values are displayed by default in tree output. Running `ssmtree
/app/prod` on a shared screen, in a pair-programming session, or in a terminal
with scrollback could expose sensitive configuration values to unauthorized
viewers — even non-SecureString values like database hostnames, ports, and
internal URLs.

**Risk:** Inadvertent exposure of sensitive configuration during screen sharing,
demos, or shoulder surfing.

**Recommendation:**
1. Change the default to `--hide-values`. Users who want to see values must
   explicitly pass `--show-values`.
2. Alternatively, hide only `SecureString` values by default, and show
   `String`/`StringList` values.

---

### M3 — No Rate Limiting on AWS API Calls During Copy

**Location:** `src/ssmtree/copier.py:74-88`

**Description:**
The copy operation calls `put_parameter` in a tight loop with no rate limiting,
backoff, or retry logic. For namespaces with hundreds of parameters, this will
likely hit the SSM API throttling limit (40 TPS for standard parameters),
causing `ThrottlingException` errors and partial copy failures.

**Risk:** Copy operations on large namespaces will fail partway through,
exacerbated by the non-atomic issue (H3).

**Recommendation:**
1. Add exponential backoff retry logic for `ThrottlingException` (boto3's
   built-in retry config may be sufficient — configure
   `config=Config(retries={"max_attempts": 5, "mode": "adaptive"})`).
2. Optionally add a configurable delay between writes (`--delay-ms`).

---

### M4 — No Input Validation on Path Arguments

**Location:** `src/ssmtree/cli.py` (all commands)

**Description:**
Path arguments (`path`, `path1`, `path2`, `source`, `dest`) are passed directly
to the AWS SSM API without local validation. While SSM itself rejects malformed
paths, this means:

- Invalid paths generate confusing AWS error messages rather than clear CLI
  errors.
- Paths without a leading `/` will fail with an unhelpful API error.
- Empty strings or whitespace-only strings are not caught.

**Risk:** Poor user experience and confusing error messages; no direct security
exploit, but lack of input validation is a defense-in-depth gap.

**Recommendation:**
1. Validate that all path arguments start with `/` and match
   `^/[a-zA-Z0-9_./-]+$` (the SSM parameter name constraints).
2. Reject empty or whitespace-only paths with a clear error message.
3. Use a Click callback or custom type for path validation.

---

### M5 — Diff Output Exposes Values From Both Namespaces

**Location:** `src/ssmtree/formatters.py:111-122`, `src/ssmtree/cli.py:184-198`

**Description:**
The diff table and diff JSON both display actual parameter values from both
namespaces. This is particularly sensitive when comparing production with
staging — it exposes production secrets alongside staging values.

**Risk:** When used in automation or shared contexts, the diff reveals secrets
from both environments simultaneously.

**Recommendation:**
1. Respect the `--show-values/--hide-values` flag in the diff command as well.
2. In diff mode, consider showing only whether values differ (changed/unchanged)
   rather than the actual values, unless `--show-values` is explicitly provided.

---

## LOW Severity Findings

### L1 — `.gitignore` Does Not Exclude `.env` Files

**Location:** `.gitignore`

**Description:**
While `.aws/` is correctly gitignored, the common `.env`, `.env.local`, and
`.env.*` patterns are not listed. Contributors who store AWS credentials or
other secrets in `.env` files could accidentally commit them.

**Recommendation:**
Add the following to `.gitignore`:
```
.env
.env.*
.env.local
```

---

### L2 — Test Fixtures Contain Realistic-Looking Credentials

**Location:** `tests/fixtures/parameters.json`, `tests/conftest.py`

**Description:**
Test fixtures use values like `"s3cr3t!"`, `"api-key-prod-abc123"`, and
`"api-key-staging-xyz789"`. While these are not real credentials, they are
realistic enough to trigger secret-scanning tools (e.g., GitHub secret scanning,
truffleHog, detect-secrets) and could establish a pattern that developers copy
with real values.

**Recommendation:**
1. Use obviously fake values like `"FAKE-test-password"`,
   `"TEST-api-key-not-real"`.
2. Add a `.pre-commit` hook or CI step running a secret scanner (e.g.,
   `detect-secrets`).

---

### L3 — No Dependency Vulnerability Scanning in CI

**Location:** `.github/workflows/ci.yml`

**Description:**
While Dependabot is configured for weekly updates, the CI pipeline does not
actively scan installed dependencies for known vulnerabilities. A vulnerable
transitive dependency could go unnoticed between Dependabot runs.

**Recommendation:**
Add a CI step that runs `pip-audit` or `safety check`:
```yaml
- name: Audit dependencies
  run: pip install pip-audit && pip-audit
```

---

### L4 — CI Does Not Pin Action Versions by SHA

**Location:** `.github/workflows/ci.yml:18-22`

**Description:**
GitHub Actions are referenced by tag (`@v4`, `@v5`) rather than by commit SHA.
A compromised upstream action could inject malicious code into the CI pipeline.

**Recommendation:**
Pin actions by full SHA for supply-chain security:
```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
- uses: actions/setup-python@82c7e631bb3cdc910f68e0081d67478d79c6982d  # v5.0.0
```

---

### L5 — No Type Validation on `Parameter.type` Field

**Location:** `src/ssmtree/models.py:16`

**Description:**
The `type` field on `Parameter` is a plain `str` with no validation. It could
contain any string value, though it should only be `"String"`,
`"SecureString"`, or `"StringList"`. An unexpected type value from a malformed
API response would be silently accepted.

**Recommendation:**
Use a `Literal["String", "SecureString", "StringList"]` type annotation and
optionally validate in `__post_init__`.

---

## Positive Security Observations

The following aspects of the codebase demonstrate good security practices:

1. **No custom cryptography** — all encryption/decryption is delegated to AWS
   KMS via the boto3 SDK.
2. **No file writes in production code** — the tool only reads from SSM and
   writes to SSM; it never writes to the local filesystem.
3. **No shell command execution** — no `subprocess`, `os.system`, or similar
   calls anywhere in the codebase.
4. **No user-supplied data in format strings** — Rich markup and Click output
   do not use f-strings with unsanitized user data in dangerous contexts.
5. **Clean dependency set** — only 3 production dependencies (click, rich,
   boto3), all well-maintained and widely audited.
6. **Proper AWS credential handling** — credentials are resolved entirely
   through boto3's standard chain; no credentials are hardcoded or read from
   config files.
7. **Comprehensive test coverage (94%)** — including tests for error paths and
   edge cases.
8. **Dependabot enabled** — automated dependency updates for both pip and
   GitHub Actions.
9. **SECURITY.md with responsible disclosure process** — clear vulnerability
   reporting guidelines.
10. **`.gitignore` excludes `.aws/`** — prevents accidental credential commits.
11. **`mypy --strict` enabled** — static type checking catches a class of bugs
    at development time.
12. **`moto` used for AWS mocking in tests** — no real AWS calls in the test
    suite.

---

## Summary of Recommendations (Prioritized)

| Priority | ID | Action |
|----------|----|--------|
| 1 | H1 | Redact SecureString values in JSON output by default |
| 2 | H2 | Add interactive confirmation before copy writes |
| 3 | H3 | Add error handling and recovery reporting to copy loop |
| 4 | M2 | Change default to `--hide-values` |
| 5 | M1 | Sanitize AWS error messages in user-facing output |
| 6 | M5 | Respect `--hide-values` in diff output |
| 7 | M3 | Add retry/backoff logic for SSM API throttling |
| 8 | M4 | Validate path arguments locally before API calls |
| 9 | L1 | Add `.env*` patterns to `.gitignore` |
| 10 | L3 | Add `pip-audit` to CI pipeline |
| 11 | L4 | Pin GitHub Actions by commit SHA |
| 12 | L2 | Use obviously fake values in test fixtures |
| 13 | L5 | Add type validation to `Parameter.type` field |
