"""Tests for ssmtree.putter."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from ssmtree.putter import PutError, _sanitize_error, put_parameter


@pytest.fixture(autouse=True)
def aws_env():
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


class TestPutParameter:
    @mock_aws
    def test_creates_string_parameter(self):
        client = boto3.client("ssm", region_name="us-east-1")
        version = put_parameter("/app/test/key", "my-value", "String", client)

        assert version == 1
        resp = client.get_parameter(Name="/app/test/key")
        assert resp["Parameter"]["Value"] == "my-value"
        assert resp["Parameter"]["Type"] == "String"

    @mock_aws
    def test_creates_secure_string_parameter(self):
        client = boto3.client("ssm", region_name="us-east-1")
        version = put_parameter("/app/test/secret", "s3cret", "SecureString", client)

        assert version == 1
        resp = client.get_parameter(Name="/app/test/secret", WithDecryption=True)
        assert resp["Parameter"]["Value"] == "s3cret"
        assert resp["Parameter"]["Type"] == "SecureString"

    @mock_aws
    def test_creates_string_list_parameter(self):
        client = boto3.client("ssm", region_name="us-east-1")
        version = put_parameter(
            "/app/test/ips", "10.0.0.1,10.0.0.2", "StringList", client
        )

        assert version == 1
        resp = client.get_parameter(Name="/app/test/ips")
        assert resp["Parameter"]["Value"] == "10.0.0.1,10.0.0.2"
        assert resp["Parameter"]["Type"] == "StringList"

    @mock_aws
    def test_returns_version_number(self):
        client = boto3.client("ssm", region_name="us-east-1")
        v1 = put_parameter("/app/test/key", "val1", "String", client)
        assert v1 == 1

        v2 = put_parameter(
            "/app/test/key", "val2", "String", client, overwrite=True
        )
        assert v2 == 2

    @mock_aws
    def test_overwrite_false_raises_on_existing(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter("/app/test/key", "original", "String", client)

        with pytest.raises(PutError):
            put_parameter("/app/test/key", "new", "String", client, overwrite=False)

    @mock_aws
    def test_overwrite_true_updates_value(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter("/app/test/key", "original", "String", client)
        put_parameter("/app/test/key", "updated", "String", client, overwrite=True)

        resp = client.get_parameter(Name="/app/test/key")
        assert resp["Parameter"]["Value"] == "updated"

    @mock_aws
    def test_description_is_set(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter(
            "/app/test/key",
            "val",
            "String",
            client,
            description="A test parameter",
        )

        resp = client.describe_parameters(
            ParameterFilters=[{"Key": "Name", "Values": ["/app/test/key"]}]
        )
        params = resp["Parameters"]
        assert len(params) == 1
        assert params[0]["Description"] == "A test parameter"

    @mock_aws
    def test_kms_key_id_passed_for_secure_string(self):
        client = boto3.client("ssm", region_name="us-east-1")
        # moto accepts any kms key id; we just verify no error is raised
        version = put_parameter(
            "/app/test/secret",
            "val",
            "SecureString",
            client,
            kms_key_id="alias/my-key",
        )
        assert version >= 1

    @mock_aws
    def test_put_error_wraps_client_error(self):
        client = boto3.client("ssm", region_name="us-east-1")
        # Create a param, then try to overwrite without overwrite=True
        client.put_parameter(Name="/app/key", Value="v", Type="String")
        with pytest.raises(PutError):
            put_parameter("/app/key", "new", "String", client, overwrite=False)


class TestSanitizeError:
    """Fix #2: error messages must not leak secret values, ARNs, or account IDs."""

    def test_strips_parameter_value(self):
        msg = "An error occurred: value=TopSecretPassword123 is invalid"
        result = _sanitize_error(msg, "TopSecretPassword123")
        assert "TopSecretPassword123" not in result
        assert "***" in result

    def test_strips_arn(self):
        msg = "Access denied for arn:aws:ssm:us-east-1:123456789012:parameter/key"
        result = _sanitize_error(msg, "val")
        assert "123456789012" not in result
        assert "arn:***" in result

    def test_strips_account_id(self):
        msg = "Account 123456789012 does not have permission"
        result = _sanitize_error(msg, "val")
        assert "123456789012" not in result

    def test_strips_value_and_arn_together(self):
        msg = (
            "Error putting my-secret to "
            "arn:aws:ssm:us-east-1:123456789012:parameter/key"
        )
        result = _sanitize_error(msg, "my-secret")
        assert "my-secret" not in result
        assert "123456789012" not in result

    def test_empty_value_is_safe(self):
        msg = "Some error"
        result = _sanitize_error(msg, "")
        assert result == "Some error"
