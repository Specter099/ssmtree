"""Shared pytest fixtures for ssmtree tests."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def raw_parameters() -> list[dict]:
    """Load raw parameter dicts from the JSON fixture file."""
    with open(FIXTURES_DIR / "parameters.json") as fh:
        return json.load(fh)


@pytest.fixture()
def aws_credentials():
    """Ensure moto doesn't try to use real AWS credentials."""
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


@pytest.fixture()
def ssm_client(aws_credentials):
    """A moto-mocked SSM client with fixture parameters pre-loaded."""
    with mock_aws():
        client = boto3.client("ssm", region_name="us-east-1")
        # Seed parameters from fixture file
        with open(FIXTURES_DIR / "parameters.json") as fh:
            params = json.load(fh)
        for item in params:
            put_kwargs = {
                "Name": item["Name"],
                "Value": item["Value"],
                "Type": item["Type"],
            }
            client.put_parameter(**put_kwargs)
        yield client


@pytest.fixture()
def prod_params():
    """Return Parameter objects for the /app/prod namespace."""
    from ssmtree.models import Parameter

    return [
        Parameter(
            path="/app/prod/db/host",
            name="host",
            value="prod-db.example.com",
            type="String",
            version=1,
            last_modified=datetime(2024, 1, 15, tzinfo=UTC),
        ),
        Parameter(
            path="/app/prod/db/port",
            name="port",
            value="5432",
            type="String",
            version=2,
            last_modified=datetime(2024, 1, 16, tzinfo=UTC),
        ),
        Parameter(
            path="/app/prod/db/password",
            name="password",
            value="FAKE-test-password",
            type="SecureString",
            version=3,
            last_modified=datetime(2024, 1, 17, tzinfo=UTC),
        ),
        Parameter(
            path="/app/prod/api/key",
            name="key",
            value="TEST-api-key-not-real",
            type="SecureString",
            version=1,
            last_modified=datetime(2024, 1, 18, tzinfo=UTC),
        ),
        Parameter(
            path="/app/prod/api/allowed_ips",
            name="allowed_ips",
            value="10.0.0.1,10.0.0.2,10.0.0.3",
            type="StringList",
            version=1,
            last_modified=datetime(2024, 1, 18, tzinfo=UTC),
        ),
        Parameter(
            path="/app/prod/feature_flags",
            name="feature_flags",
            value="dark_mode,beta_ui",
            type="StringList",
            version=1,
            last_modified=datetime(2024, 1, 19, tzinfo=UTC),
        ),
    ]


@pytest.fixture()
def staging_params():
    """Return Parameter objects for the /app/staging namespace."""
    from ssmtree.models import Parameter

    return [
        Parameter(
            path="/app/staging/db/host",
            name="host",
            value="staging-db.example.com",
            type="String",
            version=1,
            last_modified=datetime(2024, 1, 15, tzinfo=UTC),
        ),
        Parameter(
            path="/app/staging/db/port",
            name="port",
            value="5432",
            type="String",
            version=1,
            last_modified=datetime(2024, 1, 15, tzinfo=UTC),
        ),
        Parameter(
            path="/app/staging/db/password",
            name="password",
            value="FAKE-staging-password",
            type="SecureString",
            version=1,
            last_modified=datetime(2024, 1, 15, tzinfo=UTC),
        ),
        Parameter(
            path="/app/staging/api/key",
            name="key",
            value="TEST-staging-key-not-real",
            type="SecureString",
            version=1,
            last_modified=datetime(2024, 1, 15, tzinfo=UTC),
        ),
    ]
