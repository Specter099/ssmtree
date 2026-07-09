# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-07-09

### Security

- **copy**: refuse to copy `SecureString` parameters without `--decrypt`.
  Previously the source KMS ciphertext was written back as the destination
  value and silently re-encrypted, corrupting the secret.
- Route all `copy` error messages through the shared sanitizer so ARNs,
  account IDs, and secret values are stripped (previously only fetch/put
  scrubbed errors).
- Move the `--include-secrets` warning to stderr so it no longer contaminates
  JSON emitted on stdout.
- CI: add a least-privilege `permissions: contents: read` block, SHA-pin the
  publish and Claude workflows, drop `secrets: inherit` from the backup
  workflow, and add a pinned dependency graph (`constraints-dev.txt`).

### Added

- `put` command to write a single parameter (`String`/`SecureString`/`StringList`),
  with `--stdin` for secret input and overwrite confirmation.
- `--endpoint-url` option on all commands for localstack / custom endpoints.
- Client-creation failures (unknown profile, unresolved region) now abort with
  a clean message instead of a raw traceback.
- Copy plan and diff output flag `SecureString` rows that require `--decrypt`.

### Changed

- `copy` now exits non-zero when one or more parameters fail to write.
- Shared `ssmtree.errors` module centralizes error sanitization.
- Enforce `mypy --strict` and a coverage floor in CI.

## [0.3.1]

### Changed

- Show parameter values by default; `SecureString` values always render as
  `[redacted]` unless explicitly decrypted.

## [0.3.0]

### Added

- Redact `SecureString` values in `diff` table output.

## [0.2.0]

### Added

- Show `[redacted]` for `SecureString` values in tree output.

## [0.1.0] - 2026-02-25

### Added

- Tree view of SSM Parameter Store with colorized output
- `diff` command to compare two parameter namespaces
- `copy` command with dry-run and overwrite support
- Glob pattern filtering (`--filter`)
- JSON output format (`--output json`)
- SecureString decryption (`--decrypt`)
- AWS profile and region selection
- 86 tests with 94% coverage

[0.4.0]: https://github.com/Specter099/ssmtree/releases/tag/v0.4.0
[0.1.0]: https://github.com/Specter099/ssmtree/releases/tag/v0.1.0
