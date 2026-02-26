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
            result = runner.invoke(
                main, ["--output", "json", "--include-secrets", "/app/prod"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        secure = [item for item in data if item["type"] == "SecureString"]
        assert len(secure) == 1
        assert secure[0]["value"] == "FAKE-test-password"

    def test_values_hidden_by_default(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            result = runner.invoke(main, ["/app/prod"])
        assert result.exit_code == 0
        assert "prod-host" not in result.output

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
            result = runner.invoke(
                main, ["diff", "--output", "json", "/app/prod", "/app/staging"]
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "added" in data
        assert "removed" in data
        assert "changed" in data

    def test_diff_json_redacts_secure_strings_by_default(self, runner):
        prod = [_param("/prod/secret", "top-secret", "SecureString")]
        staging = [_param("/staging/secret", "also-secret", "SecureString")]
        with patch("ssmtree.cli.fetch_parameters", side_effect=[prod, staging]):
            result = runner.invoke(
                main, ["diff", "--output", "json", "/prod", "/staging"]
            )
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
            result = runner.invoke(
                main, ["copy", "--dry-run", "/app/prod", "/app/staging"]
            )
        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry" in result.output.lower()

    def test_dry_run_does_not_call_boto3(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.boto3") as mock_boto:
                result = runner.invoke(
                    main, ["copy", "--dry-run", "/app/prod", "/app/staging"]
                )
        assert result.exit_code == 0
        # boto3.Session should NOT have been called on dry run
        mock_boto.Session.assert_not_called()

    def test_empty_source_shows_message(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=[]):
            result = runner.invoke(main, ["copy", "/app/prod", "/app/staging"])
        assert result.exit_code == 0
        assert "No parameters" in result.output

    def test_copy_invokes_copy_namespace(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.boto3"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(["/staging/a"], []),
                ) as mock_copy:
                    result = runner.invoke(
                        main, ["copy", "--yes", "/app/prod", "/app/staging"]
                    )
        assert result.exit_code == 0
        mock_copy.assert_called_once()

    def test_copy_without_yes_prompts(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.boto3"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(["/staging/a"], []),
                ):
                    # Respond 'n' to the confirmation prompt
                    result = runner.invoke(
                        main, ["copy", "/app/prod", "/app/staging"], input="n\n"
                    )
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_copy_validates_paths(self, runner):
        result = runner.invoke(main, ["copy", "no-slash", "/staging"])
        assert result.exit_code != 0

    def test_copy_reports_failures(self, runner):
        with patch("ssmtree.cli.fetch_parameters", return_value=PROD_PARAMS):
            with patch("ssmtree.cli.boto3"):
                with patch(
                    "ssmtree.cli.copy_namespace",
                    return_value=(
                        ["/staging/a"],
                        [("/staging/b", "AccessDenied")],
                    ),
                ):
                    result = runner.invoke(
                        main, ["copy", "--yes", "/app/prod", "/app/staging"]
                    )
        assert result.exit_code == 0
        assert "Failed 1" in result.output
