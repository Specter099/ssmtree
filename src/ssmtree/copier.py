"""Copy an SSM parameter namespace to a new prefix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from ssmtree.models import Parameter

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient


def _rewrite_path(path: str, source_prefix: str, dest_prefix: str) -> str:
    source_prefix = source_prefix.rstrip("/")
    dest_prefix = dest_prefix.rstrip("/")
    if path.startswith(source_prefix + "/"):
        return dest_prefix + path[len(source_prefix) :]
    if path == source_prefix:
        return dest_prefix
    return path


def copy_namespace(
    source_params: list[Parameter],
    source_prefix: str,
    dest_prefix: str,
    ssm_client: SSMClient,
    overwrite: bool = False,
    dry_run: bool = False,
    kms_key_id: str | None = None,
) -> list[str]:
    """Copy all parameters from *source_prefix* to *dest_prefix*.

    Each parameter's path is rewritten: the *source_prefix* portion is
    replaced with *dest_prefix* while the relative suffix is preserved.

    Args:
        source_params:  Parameters fetched from *source_prefix*.
        source_prefix:  The prefix to strip when rewriting paths.
        dest_prefix:    The new prefix to prepend.
        ssm_client:     A boto3 SSM client.
        overwrite:      Allow overwriting existing destination parameters.
        dry_run:        If *True*, return the planned dest paths without writing.
        kms_key_id:     KMS key ARN/alias for ``SecureString`` parameters at dest.
                        Defaults to the account default CMK.

    Returns:
        List of destination paths that were written (or would be written on dry-run).
    """
    planned: list[str] = []
    for param in sorted(source_params, key=lambda p: p.path):
        dest_path = _rewrite_path(param.path, source_prefix, dest_prefix)
        planned.append(dest_path)

    if dry_run:
        return planned

    console = Console()
    written: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Copying parameters…", total=len(source_params))

        for param, dest_path in zip(
            sorted(source_params, key=lambda p: p.path), planned
        ):
            put_kwargs: dict[str, Any] = {
                "Name": dest_path,
                "Value": param.value,
                "Type": param.type,
                "Overwrite": overwrite,
            }
            if param.type == "SecureString" and kms_key_id:
                put_kwargs["KeyId"] = kms_key_id

            ssm_client.put_parameter(**put_kwargs)
            written.append(dest_path)
            progress.advance(task)

    return written
