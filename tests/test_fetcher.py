"""Tests for ssmtree.fetcher."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from ssmtree.fetcher import FetchError, _sanitize_error, fetch_parameters
from ssmtree.models import Parameter


@pytest.fixture(autouse=True)
def aws_env():
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


@mock_aws
def test_fetch_basic():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/app/prod/db/host", Value="localhost", Type="String")
    client.put_parameter(Name="/app/prod/db/port", Value="5432", Type="String")

    params = fetch_parameters("/app/prod")

    assert len(params) == 2
    paths = {p.path for p in params}
    assert "/app/prod/db/host" in paths
    assert "/app/prod/db/port" in paths


@mock_aws
def test_fetch_returns_sorted():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/z/b", Value="b", Type="String")
    client.put_parameter(Name="/z/a", Value="a", Type="String")

    params = fetch_parameters("/z")

    assert params[0].path == "/z/a"
    assert params[1].path == "/z/b"


@mock_aws
def test_fetch_returns_parameter_objects():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/app/key", Value="myval", Type="String")

    params = fetch_parameters("/app")

    assert len(params) == 1
    p = params[0]
    assert isinstance(p, Parameter)
    assert p.path == "/app/key"
    assert p.name == "key"
    assert p.value == "myval"
    assert p.type == "String"


@mock_aws
def test_fetch_secure_string_without_decrypt():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/app/secret", Value="mysecret", Type="SecureString")

    # moto returns the value regardless of WithDecryption for SecureString,
    # but the type should still be SecureString
    params = fetch_parameters("/app", decrypt=False)

    assert len(params) == 1
    assert params[0].type == "SecureString"


@mock_aws
def test_fetch_empty_prefix_returns_empty():
    # Nothing seeded under /nonexistent
    params = fetch_parameters("/nonexistent")
    assert params == []


@mock_aws
def test_fetch_name_is_leaf_segment():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/a/b/c/leaf", Value="v", Type="String")

    params = fetch_parameters("/a")

    assert params[0].name == "leaf"


@mock_aws
def test_fetch_multiple_types():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/x/str", Value="s", Type="String")
    client.put_parameter(Name="/x/sec", Value="s", Type="SecureString")
    client.put_parameter(Name="/x/lst", Value="a,b,c", Type="StringList")

    params = fetch_parameters("/x")
    types = {p.name: p.type for p in params}

    assert types["str"] == "String"
    assert types["sec"] == "SecureString"
    assert types["lst"] == "StringList"


@mock_aws
def test_fetch_invalid_region_raises_fetch_error(monkeypatch):
    """Simulate a boto3/botocore error being raised as FetchError."""
    from botocore.exceptions import ClientError

    import ssmtree.fetcher as fetcher_module

    def bad_client(*args, **kwargs):
        class ErrorClient:
            def get_parameters_by_path(self, **kwargs):
                raise ClientError(
                    {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
                    "GetParametersByPath",
                )

        return ErrorClient()

    monkeypatch.setattr(fetcher_module, "_make_client", bad_client)

    with pytest.raises(FetchError):
        fetch_parameters("/app")


@mock_aws
def test_fetch_exact_leaf_parameter():
    """get_parameters_by_path never returns a param AT the prefix; fallback should find it."""
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/test", Value="leaf-value", Type="String")

    params = fetch_parameters("/test")

    assert len(params) == 1
    assert params[0].path == "/test"
    assert params[0].name == "test"
    assert params[0].value == "leaf-value"


@mock_aws
def test_fetch_exact_leaf_not_returned_when_children_also_exist():
    """When /prefix has both itself and children, both should be returned."""
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/app", Value="root-value", Type="String")
    client.put_parameter(Name="/app/key", Value="child-value", Type="String")

    params = fetch_parameters("/app")
    paths = {p.path for p in params}

    assert "/app" in paths
    assert "/app/key" in paths


@mock_aws
def test_fetch_nonexistent_leaf_returns_empty():
    """Querying a path that doesn't exist should return empty list, not raise."""
    params = fetch_parameters("/does/not/exist")
    assert params == []


@mock_aws
def test_fetch_exact_leaf_secure_string():
    """Fallback get_parameter should respect the decrypt flag for SecureString."""
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/app/secret", Value="mysecret", Type="SecureString")

    params = fetch_parameters("/app/secret", decrypt=False)

    assert len(params) == 1
    assert params[0].type == "SecureString"
    assert params[0].path == "/app/secret"


class TestSanitizeError:
    def test_strips_arns(self):
        msg = "Error with arn:aws:ssm:us-east-1:123456789012:parameter/foo"
        result = _sanitize_error(msg)
        assert "123456789012" not in result
        assert "arn:***" in result

    def test_strips_account_ids(self):
        msg = "Account 123456789012 does not have access"
        result = _sanitize_error(msg)
        assert "123456789012" not in result
        assert "***" in result

    def test_preserves_non_sensitive_content(self):
        msg = "Access denied for GetParametersByPath"
        result = _sanitize_error(msg)
        assert result == msg
