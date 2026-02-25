"""Fetch parameters from AWS SSM Parameter Store."""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ssmtree.models import Parameter

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient


class FetchError(Exception):
    """Raised when the SSM API call fails."""


def _make_client(profile: str | None, region: str | None) -> SSMClient:
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("ssm")  # type: ignore[return-value]


def fetch_parameters(
    prefix: str,
    decrypt: bool = False,
    profile: str | None = None,
    region: str | None = None,
) -> list[Parameter]:
    """Fetch all SSM parameters under *prefix* (recursive).

    Args:
        prefix: SSM path prefix, e.g. "/" or "/app/prod".
        decrypt: If True, decrypt SecureString values.
        profile: AWS named profile to use.
        region: AWS region override.

    Returns:
        List of :class:`Parameter` objects sorted by path.

    Raises:
        FetchError: On any AWS API error.
    """
    client = _make_client(profile, region)
    params: list[Parameter] = []
    kwargs: dict = {
        "Path": prefix,
        "Recursive": True,
        "WithDecryption": decrypt,
    }

    try:
        while True:
            response = client.get_parameters_by_path(**kwargs)
            for item in response.get("Parameters", []):
                path = item["Name"]
                segments = [s for s in path.split("/") if s]
                name = segments[-1] if segments else path
                params.append(
                    Parameter(
                        path=path,
                        name=name,
                        value=item.get("Value", ""),
                        type=item.get("Type", "String"),
                        version=item.get("Version", 0),
                        last_modified=item.get("LastModifiedDate"),
                    )
                )
            next_token = response.get("NextToken")
            if not next_token:
                break
            kwargs["NextToken"] = next_token
    except (ClientError, BotoCoreError) as exc:
        raise FetchError(f"Failed to fetch parameters from SSM: {exc}") from exc

    return sorted(params, key=lambda p: p.path)
