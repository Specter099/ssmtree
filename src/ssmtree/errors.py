"""Shared error types and message sanitization for ssmtree."""

from __future__ import annotations

import re

_ARN_RE = re.compile(r"arn:aws[a-zA-Z-]*:[a-zA-Z0-9-]+:\S+")
_ACCOUNT_RE = re.compile(r"\b\d{12}\b")


class ClientCreationError(Exception):
    """Raised when a boto3 SSM client cannot be created.

    Typically caused by an unknown ``--profile`` or an unresolved region.
    """


def sanitize_error(msg: str, value: str | None = None) -> str:
    """Strip ARNs, AWS account IDs, and an optional secret value from *msg*.

    AWS error messages routinely embed the caller's ARN and account ID, and
    write errors may echo the parameter value. This scrubs all three so error
    output shown to the user does not leak identifiers or secrets.
    """
    msg = _ARN_RE.sub("arn:***", msg)
    msg = _ACCOUNT_RE.sub("***", msg)
    if value:
        msg = msg.replace(value, "***")
    return msg
