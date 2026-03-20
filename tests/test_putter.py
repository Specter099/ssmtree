"""Tests for ssmtree.putter."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from ssmtree.putter import PutError, put_parameter


@pytest.fixture(autouse=True)
def aws_env():
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


class TestPutParameter:
    @mock_aws
    def test_writes_string_parameter(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter("/app/prod/db/host", "my-host", ssm_client=client)
        response = client.get_parameter(Name="/app/prod/db/host")
        assert response["Parameter"]["Value"] == "my-host"

    @mock_aws
    def test_returns_version_number(self):
        client = boto3.client("ssm", region_name="us-east-1")
        version = put_parameter("/app/prod/key", "val", ssm_client=client)
        assert version == 1

    @mock_aws
    def test_writes_secure_string(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter("/app/prod/secret", "s3cr3t", param_type="SecureString", ssm_client=client)
        response = client.get_parameter(Name="/app/prod/secret", WithDecryption=True)
        assert response["Parameter"]["Type"] == "SecureString"
        assert response["Parameter"]["Value"] == "s3cr3t"

    @mock_aws
    def test_writes_string_list(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter(
            "/app/prod/ips", "1.2.3.4,5.6.7.8", param_type="StringList", ssm_client=client
        )
        response = client.get_parameter(Name="/app/prod/ips")
        assert response["Parameter"]["Type"] == "StringList"

    @mock_aws
    def test_overwrite_false_raises_put_error(self):
        client = boto3.client("ssm", region_name="us-east-1")
        client.put_parameter(Name="/app/prod/key", Value="old", Type="String")
        with pytest.raises(PutError, match="already exists"):
            put_parameter("/app/prod/key", "new", overwrite=False, ssm_client=client)

    @mock_aws
    def test_overwrite_false_error_mentions_flag(self):
        client = boto3.client("ssm", region_name="us-east-1")
        client.put_parameter(Name="/app/prod/key", Value="old", Type="String")
        with pytest.raises(PutError, match="--overwrite"):
            put_parameter("/app/prod/key", "new", overwrite=False, ssm_client=client)

    @mock_aws
    def test_overwrite_true_succeeds(self):
        client = boto3.client("ssm", region_name="us-east-1")
        client.put_parameter(Name="/app/prod/key", Value="old", Type="String")
        put_parameter("/app/prod/key", "new", overwrite=True, ssm_client=client)
        response = client.get_parameter(Name="/app/prod/key")
        assert response["Parameter"]["Value"] == "new"

    @mock_aws
    def test_overwrite_updates_version(self):
        client = boto3.client("ssm", region_name="us-east-1")
        client.put_parameter(Name="/app/prod/key", Value="old", Type="String")
        version = put_parameter("/app/prod/key", "new", overwrite=True, ssm_client=client)
        assert version == 2

    @mock_aws
    def test_with_description(self):
        client = boto3.client("ssm", region_name="us-east-1")
        put_parameter("/app/prod/key", "val", description="My param", ssm_client=client)
        response = client.describe_parameters(
            ParameterFilters=[{"Key": "Name", "Values": ["/app/prod/key"]}]
        )
        assert response["Parameters"][0]["Description"] == "My param"

    @mock_aws
    def test_kms_key_id_passed_for_secure_string(self):
        """KMS key should be accepted without error for SecureString (moto accepts it)."""
        client = boto3.client("ssm", region_name="us-east-1")
        # moto accepts any kms_key_id string; just verify the call succeeds
        version = put_parameter(
            "/app/prod/secret", "val",
            param_type="SecureString",
            kms_key_id="alias/my-key",
            ssm_client=client,
        )
        assert version == 1

    @mock_aws
    def test_kms_key_id_ignored_for_string(self):
        """kms_key_id should not be included in the API call for String type."""
        client = boto3.client("ssm", region_name="us-east-1")
        # Should succeed without error even if kms_key_id is provided for String
        version = put_parameter(
            "/app/prod/key", "val",
            param_type="String",
            kms_key_id="alias/my-key",
            ssm_client=client,
        )
        assert version == 1

    @mock_aws
    def test_boto_core_error_raises_put_error(self, monkeypatch):
        from botocore.exceptions import BotoCoreError

        client = boto3.client("ssm", region_name="us-east-1")

        def _raise(*args, **kwargs):
            raise BotoCoreError()

        monkeypatch.setattr(client, "put_parameter", _raise)
        with pytest.raises(PutError, match="AWS API error"):
            put_parameter("/app/prod/key", "val", ssm_client=client)

    @mock_aws
    def test_client_error_sanitizes_message(self, monkeypatch):
        from botocore.exceptions import ClientError

        client = boto3.client("ssm", region_name="us-east-1")

        def _raise(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "User arn:aws:iam::123456789012:role/MyRole is not authorized",
                    }
                },
                "PutParameter",
            )

        monkeypatch.setattr(client, "put_parameter", _raise)
        with pytest.raises(PutError) as exc_info:
            put_parameter("/app/prod/key", "val", ssm_client=client)
        # ARN and account ID should be redacted
        assert "123456789012" not in str(exc_info.value)
        assert "arn:***" in str(exc_info.value) or "***" in str(exc_info.value)

    def test_raises_when_no_client(self):
        with pytest.raises(PutError, match="ssm_client is required"):
            put_parameter("/app/prod/key", "val")
