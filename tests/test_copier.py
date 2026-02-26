"""Tests for ssmtree.copier."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws

from ssmtree.copier import _rewrite_path, copy_namespace
from ssmtree.models import Parameter


def _param(path: str, value: str = "v", type_: str = "String") -> Parameter:
    segments = [s for s in path.split("/") if s]
    return Parameter(
        path=path,
        name=segments[-1] if segments else path,
        value=value,
        type=type_,
        version=1,
        last_modified=datetime(2024, 1, 1, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
def aws_env():
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


class TestRewritePath:
    def test_rewrite_simple(self):
        assert _rewrite_path("/prod/db/host", "/prod", "/staging") == "/staging/db/host"

    def test_rewrite_deep(self):
        assert (
            _rewrite_path("/a/b/c/d", "/a/b", "/x/y") == "/x/y/c/d"
        )

    def test_rewrite_exact_match(self):
        assert _rewrite_path("/prod", "/prod", "/staging") == "/staging"

    def test_rewrite_no_match_unchanged(self):
        assert _rewrite_path("/other/key", "/prod", "/staging") == "/other/key"

    def test_rewrite_strips_trailing_slash(self):
        assert _rewrite_path("/prod/key", "/prod/", "/staging/") == "/staging/key"


class TestCopyNamespace:
    @mock_aws
    def test_dry_run_returns_planned_paths(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [
            _param("/prod/db/host", "host"),
            _param("/prod/db/port", "5432"),
        ]
        written, failed = copy_namespace(
            params, "/prod", "/staging", client, dry_run=True
        )
        assert "/staging/db/host" in written
        assert "/staging/db/port" in written
        assert len(written) == 2
        assert failed == []

    @mock_aws
    def test_dry_run_does_not_write(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [_param("/prod/key", "val")]

        copy_namespace(params, "/prod", "/staging", client, dry_run=True)

        # Nothing should have been written
        response = client.get_parameters_by_path(Path="/staging", Recursive=True)
        assert response["Parameters"] == []

    @mock_aws
    def test_copy_writes_params(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [
            _param("/prod/db/host", "prod-host"),
            _param("/prod/db/port", "5432"),
        ]

        written, failed = copy_namespace(params, "/prod", "/staging", client)

        assert len(written) == 2
        assert failed == []
        response = client.get_parameters_by_path(Path="/staging", Recursive=True)
        dest_names = {p["Name"] for p in response["Parameters"]}
        assert "/staging/db/host" in dest_names
        assert "/staging/db/port" in dest_names

    @mock_aws
    def test_copy_preserves_values(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [_param("/prod/key", "my-special-value")]

        written, failed = copy_namespace(params, "/prod", "/staging", client)

        assert failed == []
        response = client.get_parameter(Name="/staging/key")
        assert response["Parameter"]["Value"] == "my-special-value"

    @mock_aws
    def test_copy_preserves_type(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [_param("/prod/key", "v", type_="StringList")]

        written, failed = copy_namespace(params, "/prod", "/staging", client)

        assert failed == []
        response = client.get_parameter(Name="/staging/key")
        assert response["Parameter"]["Type"] == "StringList"

    @mock_aws
    def test_copy_returns_written_paths(self):
        client = boto3.client("ssm", region_name="us-east-1")
        params = [_param("/prod/a"), _param("/prod/b")]

        written, failed = copy_namespace(params, "/prod", "/staging", client)

        assert set(written) == {"/staging/a", "/staging/b"}
        assert failed == []

    @mock_aws
    def test_copy_overwrite_flag(self):
        client = boto3.client("ssm", region_name="us-east-1")
        # Pre-seed destination
        client.put_parameter(Name="/staging/key", Value="old", Type="String")

        params = [_param("/prod/key", "new")]
        # Should not raise even though param exists, because overwrite=True
        written, failed = copy_namespace(params, "/prod", "/staging", client, overwrite=True)

        assert failed == []
        response = client.get_parameter(Name="/staging/key")
        assert response["Parameter"]["Value"] == "new"

    @mock_aws
    def test_empty_source_returns_empty(self):
        client = boto3.client("ssm", region_name="us-east-1")
        written, failed = copy_namespace([], "/prod", "/staging", client)
        assert written == []
        assert failed == []
