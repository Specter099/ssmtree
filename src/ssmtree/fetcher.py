"""Fetch parameters from AWS SSM Parameter Store."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ssmtree.models import Parameter

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient

_ARN_RE = re.compile(r"arn:aws[a-zA-Z-]*:[a-zA-Z0-9-]+:\S+")
_ACCOUNT_RE = re.compile(r"\b\d{12}\b")


class FetchError(Exception):
    """Raised when the SSM API call fails."""


def _sanitize_error(msg: str) -> str:
    """Strip ARNs and AWS account IDs from error messages."""
    msg = _ARN_RE.sub("arn:***", msg)
    msg = _ACCOUNT_RE.sub("***", msg)
    return msg


_RETRY_CONFIG = Config(retries={"max_attempts": 5, "mode": "adaptive"})


def _make_client(profile: str | None, region: str | None) -> SSMClient:
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client("ssm", config=_RETRY_CONFIG)  # type: ignore[return-value]


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
        sanitized = _sanitize_error(str(exc))
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
                    sanitized = _sanitize_error(str(exc))
                    raise FetchError(
                        f"Failed to fetch parameters from SSM: {sanitized}"
                    ) from exc
            except BotoCoreError as exc:
                sanitized = _sanitize_error(str(exc))
                raise FetchError(
                    f"Failed to fetch parameters from SSM: {sanitized}"
                ) from exc

    return sorted(params, key=lambda p: p.path)
