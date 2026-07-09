"""Fetch parameters from AWS SSM Parameter Store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ssmtree.errors import ClientCreationError, sanitize_error
from ssmtree.models import Parameter

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient


class FetchError(Exception):
    """Raised when the SSM API call fails."""


_RETRY_CONFIG = Config(retries={"max_attempts": 5, "mode": "adaptive"})


def make_client(
    profile: str | None,
    region: str | None,
    endpoint_url: str | None = None,
) -> SSMClient:
    """Create a boto3 SSM client with retry configuration.

    Args:
        profile:      AWS named profile to use.
        region:       AWS region override.
        endpoint_url: Custom SSM endpoint (e.g. a localstack or VPC endpoint).

    Raises:
        ClientCreationError: If the profile is unknown or no region can be
            resolved.  Callers surface this as a clean message rather than
            letting a raw botocore traceback reach the user.
    """
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client("ssm", config=_RETRY_CONFIG, endpoint_url=endpoint_url)
    except BotoCoreError as exc:
        raise ClientCreationError(sanitize_error(str(exc))) from exc


def fetch_parameters(
    prefix: str,
    decrypt: bool = False,
    profile: str | None = None,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> list[Parameter]:
    """Fetch all SSM parameters under *prefix* (recursive).

    Args:
        prefix: SSM path prefix, e.g. "/" or "/app/prod".
        decrypt: If True, decrypt SecureString values.
        profile: AWS named profile to use.
        region: AWS region override.
        endpoint_url: Custom SSM endpoint URL.

    Returns:
        List of :class:`Parameter` objects sorted by path.

    Raises:
        FetchError: On any AWS API error, including client-creation failures
            such as an unknown profile or unresolved region.
    """
    try:
        client = make_client(profile, region, endpoint_url)
    except ClientCreationError as exc:
        raise FetchError(str(exc)) from exc

    params: list[Parameter] = []
    kwargs: dict[str, Any] = {
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
        sanitized = sanitize_error(str(exc))
        raise FetchError(f"Failed to fetch parameters from SSM: {sanitized}") from exc

    # get_parameters_by_path never returns a parameter AT the prefix path itself
    # (only parameters under it).  Try get_parameter as a fallback so that
    # e.g. `ssmtree /app/db/password` works when that is a leaf parameter.
    if prefix != "/":
        existing_paths = {p.path for p in params}
        if prefix not in existing_paths:
            try:
                resp = client.get_parameter(Name=prefix, WithDecryption=decrypt)
                item = resp["Parameter"]
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
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "ParameterNotFound":
                    sanitized = sanitize_error(str(exc))
                    raise FetchError(
                        f"Failed to fetch parameters from SSM: {sanitized}"
                    ) from exc
            except BotoCoreError as exc:
                sanitized = sanitize_error(str(exc))
                raise FetchError(
                    f"Failed to fetch parameters from SSM: {sanitized}"
                ) from exc

    return sorted(params, key=lambda p: p.path)
