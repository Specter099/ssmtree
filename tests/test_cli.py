"""Tests for ssmtree.cli (Click commands via CliRunner)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ssmtree import __version__
from ssmtree.cli import main
from ssmtree.models import Parameter
from ssmtree.putter import PutError


def _param(path: str, value: str = "val", type_: str = "String") -> Parameter:
    segments = [s for s in path.split("/") if s]
    return Parameter(
        path=path,
        name=segments[-1] if segments else path,
        value=value,
        type=type_,
        version=1,
        last_modified=datetime(2024, 1, 1, tzinfo=UTC),
    )


PROD_PARAMS = [
    _param("/app/prod/db/host", "prod-host"),
    _param("/app/prod/db/port", "5432"),
    _param("/app/prod/db/password", "FAKE-test-password", "SecureString"),
]

STAGING_PARAMS = [
    _param("/app/staging/db/host", "staging-host"),
    _param("/app/staging/db/port", "5432"),
]


@pytest.fixture()
def runner():
    return CliRunner()


class TestMainCommand:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_tree_output(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod"])
        assert result.exit_code == 0
        assert "db" in result.output

    def test_json_output(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--output", "json", "/app/prod"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        paths = {item["path"] for item in data}
        assert "/app/prod/db/host" in paths

    def test_json_output_redacts_secure_strings_by_default(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--output", "json", "/app/prod"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        secure = [item for item in data if item["type"] == "SecureString"]
        assert len(secure) == 1
        assert secure[0]["value"] == "***REDACTED***"

    def test_json_output_includes_secrets_when_flagged(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--output", "json", "--include-secrets", "/app/prod"])
        assert result.exit_code == 0
        assert "WARNING" in result.output
        # Extract JSON portion (after the warning line)
        json_start = result.output.index("[")
        data = json.loads(result.output[json_start:])
        secure = [item for item in data if item["type"] == "SecureString"]
        assert len(secure) == 1
        assert secure[0]["value"] == "FAKE-test-password"

    def test_values_shown_by_default(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod"])
        assert result.exit_code == 0
        assert "prod-host" in result.output

    def test_secure_string_redacted_by_default(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod"])
        assert result.exit_code == 0
        assert "[redacted]" in result.output
        assert "FAKE-test-password" not in result.output

    def test_show_values(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--show-values", "/app/prod"])
        assert result.exit_code == 0
        assert "prod-host" in result.output

    def test_hide_values(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--hide-values", "/app/prod"])
        assert result.exit_code == 0
        assert "prod-host" not in result.output

    def test_filter_option(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["--filter", "*/db/*", "/app/prod"])
        assert result.exit_code == 0

    def test_fetch_error_exits_nonzero(self, runner):
        from ssmtree.fetcher import FetchError

        with patch("ssmtree.cli.fetch_parameters", side_effect=FetchError("denied")):
            result = runner.invoke(main, ["/app/prod"])
        assert result.exit_code != 0

    def test_default_path_is_root(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=[]) as mock_fetch:
            result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[0][0] == "/"

    def test_invalid_path_exits_nonzero(self, runner):
        result = runner.invoke(main, ["no-leading-slash"])
        assert result.exit_code != 0

    def test_path_validation_rejects_empty(self, runner):
        result = runner.invoke(main, [" "])
        assert result.exit_code != 0

    def test_decrypt_after_path_is_parsed(self, runner):
        """--decrypt placed after PATH must be parsed, not silently ignored."""
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS) as mock_fetch:
            result = runner.invoke(main, ["/app/prod", "--decrypt"])
        assert result.exit_code == 0
        assert mock_fetch.call_args[1]["decrypt"] is True

    def test_decrypt_after_path_reveals_secure_string(self, runner):
        """--decrypt after PATH should show the value, not [redacted]."""
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod", "--decrypt"])
        assert result.exit_code == 0
        assert "[redacted]" not in result.output
        assert "FAKE-test-password" in result.output

    def test_hide_values_after_path_is_parsed(self, runner):
        """--hide-values placed after PATH must be parsed."""
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod", "--hide-values"])
        assert result.exit_code == 0
        assert "prod-host" not in result.output

    def test_filter_after_path_is_parsed(self, runner):
        """--filter placed after PATH must be parsed."""
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod", "--filter", "*/db/*"])
        assert result.exit_code == 0


class TestDiffCommand:
    def test_diff_help(self, runner):
        result = runner.invoke(main, ["diff", "--help"])
        assert result.exit_code == 0
        assert "PATH1" in result.output or "path1" in result.output.lower()

    def test_diff_table_output(self, runner):
        with patch("ssmtree.cli.fetch_parameters", side_effect=[PROD_PARAMS, STAGING_PARAMS]):
            result = runner.invoke(main, ["diff", "/app/prod", "/app/staging"])
        assert result.exit_code == 0

    def test_diff_identical_shows_message(self, runner):
        same = [_param("/prod/key", "val")]
        same2 = [_param("/staging/key", "val")]
        with patch("ssmtree.cli.fetch_parameters", side_effect=[same, same2]):
            result = runner.invoke(main, ["diff", "/prod", "/staging"])
        assert result.exit_code == 0
        assert "identical" in result.output.lower()

    def test_diff_json_output(self, runner):
        with patch("ssmtree.cli.fetch_parameters", side_effect=[PROD_PARAMS, STAGING_PARAMS]):
            result = runner.invoke(main, ["diff", "--output", "json", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "added" in data
        assert "removed" in data
        assert "changed" in data

    def test_diff_json_redacts_secure_strings_by_default(self, runner):
        prod = [_param("/prod/secret", "top-secret", "SecureString")]
        staging = [_param("/staging/secret", "also-secret", "SecureString")]
        with patch("ssmtree.cli.fetch_parameters", side_effect=[prod, staging]):
            result = runner.invoke(main, ["diff", "--output", "json", "/prod", "/staging"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for entry in data["changed"]:
            assert entry["old_value"] == "***REDACTED***"
            assert entry["new_value"] == "***REDACTED***"

    def test_diff_validates_paths(self, runner):
        result = runner.invoke(main, ["diff", "no-slash", "/staging"])
        assert result.exit_code != 0


class TestCopyCommand:
    def test_copy_help(self, runner):
        result = runner.invoke(main, ["copy", "--help"])
        assert result.exit_code == 0

    def test_dry_run_shows_plan(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["copy", "--dry-run", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry" in result.output.lower()

    def test_dry_run_does_not_call_make_client(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.make_client") as mock_make:
                result = runner.invoke(main, ["copy", "--dry-run", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        mock_make.assert_not_called()

    def test_empty_source_shows_message(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=[]):
            result = runner.invoke(main, ["copy", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        assert "No parameters" in result.output

    def test_copy_invokes_copy_namespace(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.make_client"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(["/staging/a"], []),
                ) as mock_copy:
                    result = runner.invoke(main, ["copy", "--yes", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        mock_copy.assert_called_once()

    def test_copy_without_yes_prompts(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.make_client"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(["/staging/a"], []),
                ):
                    result = runner.invoke(main, ["copy", "/app/prod", "/app/staging"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_copy_validates_paths(self, runner):
        result = runner.invoke(main, ["copy", "no-slash", "/staging"])
        assert result.exit_code != 0

    def test_copy_reports_failures(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.make_client"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(
                        ["/staging/a"],
                        [("/staging/b", "AccessDenied")],
                    ),
                ):
                    result = runner.invoke(main, ["copy", "--yes", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        assert "Failed 1" in result.output


class TestPutCommand:
    def test_put_help(self, runner):
        result = runner.invoke(main, ["put", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output

    def test_put_writes_and_shows_version(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=3) as mock_put:
                result = runner.invoke(main, ["put", "/app/prod/db/host", "my-host"])
        assert result.exit_code == 0
        assert "version 3" in result.output
        mock_put.assert_called_once()

    def test_put_create_shows_created(self, runner):
        """Success message says 'Created' for new parameters."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(main, ["put", "/app/prod/key", "val"])
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_put_overwrite_shows_updated(self, runner):
        """Success message says 'Updated' when --overwrite is used."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=2):
                result = runner.invoke(
                    main, ["put", "--overwrite", "--yes", "/app/prod/key", "val"]
                )
        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_put_validates_path(self, runner):
        result = runner.invoke(main, ["put", "no-leading-slash", "val"])
        assert result.exit_code != 0

    def test_put_root_path_rejected(self, runner):
        """'/' must not be accepted as a put target."""
        result = runner.invoke(main, ["put", "/", "val"])
        assert result.exit_code != 0
        assert "root" in result.output.lower()

    def test_put_path_with_special_valid_chars(self, runner):
        """Paths with dots, underscores, and hyphens are valid."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(main, ["put", "/app/my-service_v2.0/key", "val"])
        assert result.exit_code == 0

    def test_put_path_with_invalid_chars_rejected(self, runner):
        """Paths with spaces or special characters are rejected."""
        result = runner.invoke(main, ["put", "/app/my service/key", "val"])
        assert result.exit_code != 0

    # --- Value resolution ---

    def test_put_stdin_reads_value(self, runner):
        """--stdin reads the value from stdin."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--stdin", "/app/prod/db/password"],
                    input="mysecret\n",
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["value"] == "mysecret"

    def test_put_stdin_strips_exactly_one_trailing_newline(self, runner):
        """Only one trailing newline is stripped (echo adds one)."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--stdin", "/app/prod/key"],
                    input="value\n\n",
                )
        assert result.exit_code == 0
        # The second \n should be preserved as part of the value.
        assert mock_put.call_args[1]["value"] == "value\n"

    def test_put_stdin_no_trailing_newline(self, runner):
        """Input without a trailing newline is used as-is."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--stdin", "/app/prod/key"],
                    input="value-no-newline",
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["value"] == "value-no-newline"

    def test_put_stdin_multiline_value(self, runner):
        """Multiline values from stdin are preserved (minus one trailing newline)."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--stdin", "/app/prod/key"],
                    input="line1\nline2\nline3\n",
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["value"] == "line1\nline2\nline3"

    def test_put_stdin_and_positional_value_conflict(self, runner):
        """Cannot supply both --stdin and positional VALUE."""
        result = runner.invoke(
            main,
            ["put", "--stdin", "/app/prod/key", "extra-value"],
            input="stdin-value\n",
        )
        assert result.exit_code != 0
        assert "Cannot use both" in result.output

    def test_put_stdin_empty_fails(self, runner):
        """Empty stdin must produce an error."""
        result = runner.invoke(
            main,
            ["put", "--stdin", "/app/prod/db/password"],
            input="",
        )
        assert result.exit_code != 0
        assert "No value" in result.output

    def test_put_stdin_only_newline_fails(self, runner):
        """Stdin containing only a newline (empty after strip) must fail."""
        result = runner.invoke(
            main,
            ["put", "--stdin", "/app/prod/key"],
            input="\n",
        )
        assert result.exit_code != 0
        assert "No value" in result.output

    def test_put_no_value_and_no_stdin_fails(self, runner):
        """Omitting VALUE without --stdin must fail."""
        result = runner.invoke(main, ["put", "/app/prod/key"])
        assert result.exit_code != 0
        assert "Missing" in result.output or "VALUE" in result.output

    def test_put_whitespace_only_value_is_accepted(self, runner):
        """A value of only whitespace is technically valid for SSM."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(main, ["put", "/app/prod/key", "   "])
        assert result.exit_code == 0
        assert mock_put.call_args[1]["value"] == "   "

    # --- SecureString warnings ---

    def test_put_secure_positional_warns(self, runner):
        """Passing a SecureString value as a CLI arg emits a warning."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--secure", "/app/prod/secret", "visible-secret"],
                )
        assert result.exit_code == 0
        assert "WARNING" in result.output
        assert "shell history" in result.output or "process list" in result.output

    def test_put_secure_stdin_no_warning(self, runner):
        """--stdin with --secure should NOT emit process list warning."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--secure", "--stdin", "/app/prod/secret"],
                    input="safe-secret\n",
                )
        assert result.exit_code == 0
        assert "process list" not in result.output

    # --- Overwrite confirmation ---

    def test_put_overwrite_prompts_without_yes(self, runner):
        """--overwrite without --yes prompts for confirmation."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--overwrite", "/app/prod/key", "val"],
                    input="n\n",
                )
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_put_overwrite_declined_does_not_call_put(self, runner):
        """--overwrite declined via prompt must NOT call put_parameter."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--overwrite", "/app/prod/key", "val"],
                    input="n\n",
                )
        assert result.exit_code == 0
        mock_put.assert_not_called()

    def test_put_overwrite_confirmed_proceeds(self, runner):
        """--overwrite confirmed via prompt proceeds."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=2) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--overwrite", "/app/prod/key", "val"],
                    input="y\n",
                )
        assert result.exit_code == 0
        mock_put.assert_called_once()

    def test_put_overwrite_yes_skips_prompt(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=2) as mock_put:
                result = runner.invoke(
                    main, ["put", "--overwrite", "--yes", "/app/prod/key", "val"]
                )
        assert result.exit_code == 0
        mock_put.assert_called_once()

    def test_put_overwrite_stdin_without_yes_fails(self, runner):
        """--overwrite with --stdin requires --yes (cannot prompt on piped stdin)."""
        result = runner.invoke(
            main,
            ["put", "--overwrite", "--stdin", "/app/prod/key"],
            input="some-value\n",
        )
        assert result.exit_code != 0
        assert "--yes" in result.output

    def test_put_overwrite_stdin_with_yes_succeeds(self, runner):
        """--overwrite with --stdin and --yes should work."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=2) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--overwrite", "--yes", "--stdin", "/app/prod/key"],
                    input="new-value\n",
                )
        assert result.exit_code == 0
        mock_put.assert_called_once()
        assert mock_put.call_args[1]["value"] == "new-value"

    def test_put_no_overwrite_no_prompt(self, runner):
        """Without --overwrite, no confirmation prompt is shown."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(main, ["put", "/app/prod/key", "val"])
        assert result.exit_code == 0
        mock_put.assert_called_once()
        assert "Overwrite" not in result.output

    # --- Type options ---

    def test_put_default_type_is_string(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                runner.invoke(main, ["put", "/app/prod/key", "val"])
        assert mock_put.call_args[1]["param_type"] == "String"

    def test_put_type_secure_string(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                runner.invoke(
                    main, ["put", "--type", "SecureString", "/app/prod/secret", "val"]
                )
        assert mock_put.call_args[1]["param_type"] == "SecureString"

    def test_put_type_string_list(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--type", "StringList", "/app/prod/ips", "10.0.0.1,10.0.0.2"],
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["param_type"] == "StringList"

    def test_put_secure_flag(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main, ["put", "--secure", "--stdin", "/app/prod/secret"], input="s3cret\n"
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["param_type"] == "SecureString"

    def test_secure_flag_overrides_type_option(self, runner):
        """--secure should override --type String to SecureString."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--type", "String", "--secure", "/app/prod/key", "val"],
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["param_type"] == "SecureString"

    def test_put_kms_key_id_without_secure_string_fails(self, runner):
        result = runner.invoke(
            main,
            ["put", "--kms-key-id", "alias/key", "/app/prod/key", "val"],
        )
        assert result.exit_code != 0
        assert "SecureString" in result.output

    # --- Optional parameters ---

    def test_put_with_kms_key_id(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                runner.invoke(
                    main,
                    [
                        "put", "--type", "SecureString",
                        "--kms-key-id", "alias/my-key",
                        "/app/prod/secret", "val",
                    ],
                )
        assert mock_put.call_args[1]["kms_key_id"] == "alias/my-key"

    def test_put_with_description(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                runner.invoke(
                    main,
                    ["put", "--description", "My param", "/app/prod/key", "val"],
                )
        assert mock_put.call_args[1]["description"] == "My param"

    def test_put_description_none_by_default(self, runner):
        """When --description is not provided, None is passed."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(main, ["put", "/app/prod/key", "val"])
        assert result.exit_code == 0
        assert mock_put.call_args[1]["description"] is None

    # --- Error handling ---

    def test_put_error_exits_nonzero(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", side_effect=PutError("access denied")):
                result = runner.invoke(main, ["put", "/app/prod/db/host", "my-host"])
        assert result.exit_code != 0
        assert "access denied" in result.output

    def test_put_already_exists_message(self, runner):
        with patch("ssmtree.cli.make_client"):
            with patch(
                "ssmtree.cli.put_parameter",
                side_effect=PutError(
                    "Parameter '/app/prod/db/host' already exists. Use --overwrite to replace it."
                ),
            ):
                result = runner.invoke(main, ["put", "/app/prod/db/host", "my-host"])
        assert result.exit_code != 0
        assert "already exists" in result.output

    # --- Client / connection ---

    def test_put_uses_make_client(self, runner):
        """put command uses the shared retry-configured client factory."""
        with patch("ssmtree.cli.make_client") as mock_make:
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(main, ["put", "/app/prod/key", "val"])
        assert result.exit_code == 0
        mock_make.assert_called_once()

    def test_put_forwards_profile_and_region(self, runner):
        """--profile and --region are forwarded to make_client."""
        with patch("ssmtree.cli.make_client") as mock_make:
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--profile", "myprofile", "--region", "eu-west-1",
                     "/app/prod/key", "val"],
                )
        assert result.exit_code == 0
        mock_make.assert_called_once_with("myprofile", "eu-west-1")

    # --- Full integration ---

    def test_put_secure_stdin_full_path(self, runner):
        """Full integration: --secure --stdin reads value and sets SecureString."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--secure", "--stdin", "/app/prod/secret"],
                    input="my-secret\n",
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["param_type"] == "SecureString"
        assert mock_put.call_args[1]["value"] == "my-secret"
        assert "SecureString" in result.output

    # --- Additional edge-case tests ---

    def test_put_no_overwrite_explicit_flag_behaves_like_default(self, runner):
        """Explicit --no-overwrite behaves identically to the default (no prompt)."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main, ["put", "--no-overwrite", "/app/prod/key", "val"]
                )
        assert result.exit_code == 0
        mock_put.assert_called_once()
        assert mock_put.call_args[1]["overwrite"] is False

    def test_put_empty_description_string_is_forwarded(self, runner):
        """--description '' should forward an empty string, not None."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main, ["put", "--description", "", "/app/prod/key", "val"]
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["description"] == ""

    def test_put_string_type_label_in_output(self, runner):
        """Success output includes the parameter type for String."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main, ["put", "--type", "String", "/app/prod/key", "val"]
                )
        assert result.exit_code == 0
        assert "String" in result.output

    def test_put_string_list_type_label_in_output(self, runner):
        """Success output includes the parameter type for StringList."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--type", "StringList", "/app/prod/ips", "10.0.0.1,10.0.0.2"],
                )
        assert result.exit_code == 0
        assert "StringList" in result.output

    def test_put_secure_string_type_label_in_output(self, runner):
        """Success output shows 'SecureString' for SecureString parameters."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(
                    main,
                    ["put", "--stdin", "--secure", "/app/prod/secret"],
                    input="s3cret\n",
                )
        assert result.exit_code == 0
        assert "SecureString" in result.output

    def test_put_path_with_consecutive_slashes_rejected_by_cli(self, runner):
        """Paths with consecutive slashes are rejected by the CLI."""
        result = runner.invoke(main, ["put", "//app/prod/key", "val"])
        assert result.exit_code != 0

    def test_put_path_double_slash_mid_path_rejected(self, runner):
        """A double slash in the middle of a path is rejected."""
        result = runner.invoke(main, ["put", "/app//prod/key", "val"])
        assert result.exit_code != 0

    def test_put_path_trailing_slash_rejected(self, runner):
        """A trailing slash in a path is rejected."""
        result = runner.invoke(main, ["put", "/app/prod/", "val"])
        assert result.exit_code != 0

    def test_put_path_triple_slash_prefix_rejected(self, runner):
        """A triple-slash prefix is rejected."""
        result = runner.invoke(main, ["put", "///key", "val"])
        assert result.exit_code != 0

    def test_put_path_single_segment_still_valid(self, runner):
        """A single-segment path like /key is still valid."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(main, ["put", "/key", "val"])
        assert result.exit_code == 0

    def test_put_kms_key_id_only_forwarded_for_secure_string(self, runner):
        """--kms-key-id with String type is rejected before calling put_parameter."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter") as mock_put:
                result = runner.invoke(
                    main,
                    ["put", "--type", "String", "--kms-key-id", "alias/key",
                     "/app/prod/key", "val"],
                )
        assert result.exit_code != 0
        mock_put.assert_not_called()

    def test_put_string_list_value_with_commas_forwarded_verbatim(self, runner):
        """StringList values are forwarded as-is (comma-separation is AWS's concern)."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    [
                        "put",
                        "--type",
                        "StringList",
                        "/app/prod/ips",
                        "10.0.0.1,10.0.0.2,10.0.0.3",
                    ],
                )
        assert result.exit_code == 0
        assert mock_put.call_args[1]["value"] == "10.0.0.1,10.0.0.2,10.0.0.3"

    def test_put_secure_with_kms_key_id_forwarded(self, runner):
        """--secure combined with --kms-key-id forwards the key to put_parameter."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1) as mock_put:
                result = runner.invoke(
                    main,
                    [
                        "put",
                        "--secure",
                        "--kms-key-id",
                        "arn:aws:kms:us-east-1:111122223333:key/my-key",
                        "/app/prod/secret",
                        "s3cret",
                    ],
                )
        assert result.exit_code == 0
        assert (
            mock_put.call_args[1]["kms_key_id"]
            == "arn:aws:kms:us-east-1:111122223333:key/my-key"
        )
        assert mock_put.call_args[1]["param_type"] == "SecureString"

    def test_put_single_level_path_accepted(self, runner):
        """Path with a single level (e.g. '/key') is valid."""
        with patch("ssmtree.cli.make_client"):
            with patch("ssmtree.cli.put_parameter", return_value=1):
                result = runner.invoke(main, ["put", "/key", "val"])
        assert result.exit_code == 0
