"""Write a single parameter to AWS SSM Parameter Store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError, ClientError

from ssmtree.fetcher import _sanitize_error

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient


class PutError(Exception):
    """Raised when the put_parameter call cannot proceed."""


def put_parameter(
    path: str,
    value: str,
    param_type: str = "String",
    overwrite: bool = False,
    kms_key_id: str | None = None,
    description: str | None = None,
    ssm_client: SSMClient | None = None,
) -> int:
    """Write a single SSM parameter and return the resulting version number.

    Args:
        path:        Full SSM parameter path, e.g. ``/app/prod/db/password``.
        value:       Parameter value.
        param_type:  One of ``String``, ``SecureString``, or ``StringList``.
        overwrite:   Allow overwriting an existing parameter.
        kms_key_id:  KMS key ARN/alias for ``SecureString`` encryption.
        description: Optional description stored alongside the parameter.
        ssm_client:  A boto3 SSM client.

    Returns:
        The version number of the written parameter.

    Raises:
        PutError: On any AWS API error, including ``ParameterAlreadyExists``
                  when *overwrite* is ``False``.
    """
    if ssm_client is None:
        raise PutError("ssm_client is required")

    put_kwargs: dict[str, Any] = {
        "Name": path,
        "Value": value,
        "Type": param_type,
        "Overwrite": overwrite,
    }
    if param_type == "SecureString" and kms_key_id:
        put_kwargs["KeyId"] = kms_key_id
    if description is not None:
        put_kwargs["Description"] = description

    try:
        response = ssm_client.put_parameter(**put_kwargs)
        return response["Version"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ParameterAlreadyExists":
            raise PutError(
                f"Parameter {path!r} already exists. Use --overwrite to replace it."
            ) from exc
        sanitized = _sanitize_error(str(exc))
        raise PutError(f"Failed to write parameter: {sanitized}") from exc
    except BotoCoreError as exc:
        raise PutError("AWS API error while writing parameter") from exc
