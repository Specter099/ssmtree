"""Put (create/update) a single SSM parameter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError, ClientError

from ssmtree.models import ParameterType

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient


class PutError(Exception):
    """Raised when a put_parameter call fails."""


def put_parameter(
    path: str,
    value: str,
    parameter_type: ParameterType,
    ssm_client: SSMClient,
    *,
    overwrite: bool = False,
    description: str | None = None,
    kms_key_id: str | None = None,
) -> int:
    """Create or update a single SSM parameter.

    Args:
        path:            Full SSM path, e.g. ``/app/prod/db/password``.
        value:           Parameter value.
        parameter_type:  ``"String"``, ``"SecureString"``, or ``"StringList"``.
        ssm_client:      A boto3 SSM client.
        overwrite:       Allow overwriting an existing parameter.
        description:     Optional parameter description.
        kms_key_id:      KMS key ARN/alias for ``SecureString`` encryption.

    Returns:
        The new parameter version number.

    Raises:
        PutError: On any AWS API error.
    """
    put_kwargs: dict[str, Any] = {
        "Name": path,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": overwrite,
    }
    if description is not None:
        put_kwargs["Description"] = description
    if parameter_type == "SecureString" and kms_key_id:
        put_kwargs["KeyId"] = kms_key_id

    try:
        response = ssm_client.put_parameter(**put_kwargs)
        return response["Version"]
    except (ClientError, BotoCoreError) as exc:
        raise PutError(str(exc)) from exc
