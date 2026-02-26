"""CLI entry point for ssmtree."""

from __future__ import annotations

import json
import re
import sys

import boto3
import click
from rich.console import Console

from ssmtree import __version__
from ssmtree.copier import CopyError, copy_namespace
from ssmtree.differ import diff_namespaces
from ssmtree.fetcher import FetchError, fetch_parameters
from ssmtree.formatters import render_copy_plan, render_diff, render_tree
from ssmtree.tree import build_tree, filter_tree

console = Console()

_REDACTED = "***REDACTED***"
_SSM_PATH_RE = re.compile(r"^/[a-zA-Z0-9_./-]+$")


def _abort(msg: str) -> None:
    console.print(f"[bold red]Error:[/] {msg}")
    sys.exit(1)


def _validate_path(path: str) -> None:
    """Validate that *path* looks like a valid SSM parameter path."""
    if path == "/":
        return
    if not path or not path.strip():
        _abort("Path must not be empty.")
    if not _SSM_PATH_RE.match(path):
        _abort(
            f"Invalid SSM path {path!r}. "
            "Paths must start with '/' and contain only alphanumerics, '.', '_', '-', or '/'."
        )


def _redact_value(param_type: str, value: str, include_secrets: bool) -> str:
    """Return value or redacted placeholder for SecureString parameters."""
    if param_type == "SecureString" and not include_secrets:
        return _REDACTED
    return value


class _DefaultPathGroup(click.Group):
    """Click Group that supports an optional PATH positional alongside subcommands.

    Routing strategy (decided by peeking at the first non-flag token):

    * **Subcommand mode** (first token is a known command name): stop option
      parsing at the subcommand token (``allow_interspersed_args=False``) so
      subcommand-specific options like ``--output`` are not consumed by the
      group parser.  The subcommand name goes into ``ctx._protected_args`` for
      standard Click routing.

    * **PATH mode** (first token is not a known command name, or absent):
      allow the extra positional (``allow_extra_args=True``) so PATH ends up
      in ``ctx.args``.  ``ctx._protected_args`` is left empty so
      ``invoke_without_command=True`` triggers the group callback.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Peek at the first non-flag token to choose a parsing mode.
        first_positional = next((a for a in args if not a.startswith("-")), None)

        if first_positional is not None and first_positional in self.commands:
            # Subcommand mode: stop option parsing at the subcommand name so
            # the subcommand's own options are not consumed here.
            ctx.allow_interspersed_args = False
            rest = click.Command.parse_args(self, ctx, args)
            # Put the subcommand name in _protected_args for standard routing.
            if rest:
                ctx._protected_args, ctx.args = rest[:1], rest[1:]
            else:
                ctx._protected_args, ctx.args = [], []
        else:
            # PATH mode: let the option parser consume group options, then
            # collect the remaining positional (PATH) in ctx.args.
            ctx.allow_extra_args = True
            rest = click.Command.parse_args(self, ctx, args)
            ctx._protected_args = []
            ctx.args = rest

        return ctx.args


@click.group(
    cls=_DefaultPathGroup,
    invoke_without_command=True,

)
@click.pass_context
@click.option("--decrypt", "-d", is_flag=True, default=False, help="Decrypt SecureStrings.")
@click.option("--profile", default=None, help="AWS named profile.")
@click.option("--region", default=None, help="AWS region.")
@click.option(
    "--filter", "-f", "filter_pattern", default=None, help="Glob filter on parameter paths."
)
@click.option(
    "--show-values/--hide-values",
    default=False,
    help="Show or hide parameter values (default: hide).",
)
@click.option(
    "--output",
    type=click.Choice(["tree", "json"]),
    default="tree",
    help="Output format (default: tree).",
)
@click.option(
    "--include-secrets",
    is_flag=True,
    default=False,
    help="Include SecureString values in JSON output (default: redacted).",
)
@click.version_option(__version__, "--version", "-V")
def main(
    ctx: click.Context,
    decrypt: bool,
    profile: str | None,
    region: str | None,
    filter_pattern: str | None,
    show_values: bool,
    output: str,
    include_secrets: bool,
) -> None:
    """Render AWS SSM Parameter Store as a colorized terminal tree.

    PATH (optional positional argument) defaults to "/" (the root).

    \b
    Examples:
      ssmtree /app/prod
      ssmtree --decrypt --show-values /app/prod
      ssmtree --filter "*db*" /app
      ssmtree --output json /app/prod
      ssmtree --output json --include-secrets /app/prod
    """
    if ctx.invoked_subcommand is not None:
        return

    # PATH is an optional trailing positional arg collected in ctx.args
    path = ctx.args[0] if ctx.args else "/"
    _validate_path(path)

    try:
        params = fetch_parameters(path, decrypt=decrypt, profile=profile, region=region)
    except FetchError as exc:
        _abort(str(exc))
        return

    if filter_pattern:
        tree = build_tree(params, root_path=path)
        tree = filter_tree(tree, filter_pattern)
    else:
        tree = build_tree(params, root_path=path)

    if output == "json":
        if decrypt and include_secrets:
            console.print(
                "[bold yellow]WARNING:[/] Secret values will be included in output.",
                stderr=True,
            )
        data = [
            {
                "path": p.path,
                "name": p.name,
                "value": _redact_value(p.type, p.value, include_secrets),
                "type": p.type,
                "version": p.version,
            }
            for p in params
        ]
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rich_tree = render_tree(tree, show_values=show_values)
        console.print(rich_tree)


@main.command("diff")
@click.argument("path1")
@click.argument("path2")
@click.option("--decrypt", "-d", is_flag=True, default=False, help="Decrypt SecureStrings.")
@click.option("--profile", default=None, help="AWS named profile.")
@click.option("--region", default=None, help="AWS region.")
@click.option(
    "--show-values/--hide-values",
    default=False,
    help="Show or hide parameter values in diff (default: hide).",
)
@click.option(
    "--include-secrets",
    is_flag=True,
    default=False,
    help="Include SecureString values in JSON output (default: redacted).",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table).",
)
def diff_cmd(
    path1: str,
    path2: str,
    decrypt: bool,
    profile: str | None,
    region: str | None,
    show_values: bool,
    include_secrets: bool,
    output: str,
) -> None:
    """Diff two SSM parameter namespaces.

    \b
    Examples:
      ssmtree diff /app/prod /app/staging
      ssmtree diff --decrypt --show-values /app/prod /app/staging
      ssmtree diff --decrypt --output json --include-secrets /app/prod /app/staging
    """
    _validate_path(path1)
    _validate_path(path2)

    try:
        params1 = fetch_parameters(path1, decrypt=decrypt, profile=profile, region=region)
        params2 = fetch_parameters(path2, decrypt=decrypt, profile=profile, region=region)
    except FetchError as exc:
        _abort(str(exc))
        return

    added, removed, changed = diff_namespaces(params1, params2, path1, path2)

    if output == "json":
        if decrypt and include_secrets:
            console.print(
                "[bold yellow]WARNING:[/] Secret values will be included in output.",
                stderr=True,
            )
        data = {
            "added": [
                {
                    "path": p.path,
                    "value": _redact_value(p.type, p.value, include_secrets),
                    "type": p.type,
                }
                for p in added
            ],
            "removed": [
                {
                    "path": p.path,
                    "value": _redact_value(p.type, p.value, include_secrets),
                    "type": p.type,
                }
                for p in removed
            ],
            "changed": [
                {
                    "path": old.path,
                    "old_value": _redact_value(old.type, old.value, include_secrets),
                    "new_value": _redact_value(new.type, new.value, include_secrets),
                    "type": old.type,
                }
                for old, new in changed
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if not added and not removed and not changed:
            console.print("[bold green]Namespaces are identical.[/]")
        else:
            table = render_diff(added, removed, changed, path1, path2, show_values=show_values)
            console.print(table)


@main.command("copy")
@click.argument("source")
@click.argument("dest")
@click.option(
    "--decrypt", "-d", is_flag=True, default=False, help="Decrypt SecureStrings before copying."
)
@click.option("--profile", default=None, help="AWS named profile.")
@click.option("--region", default=None, help="AWS region.")
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Overwrite existing destination parameters (default: no).",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Show what would be copied without writing."
)
@click.option(
    "--kms-key-id", default=None, help="KMS key for SecureString parameters at destination."
)
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt.")
def copy_cmd(
    source: str,
    dest: str,
    decrypt: bool,
    profile: str | None,
    region: str | None,
    overwrite: bool,
    dry_run: bool,
    kms_key_id: str | None,
    yes: bool,
) -> None:
    """Copy all SSM parameters from SOURCE to DEST namespace.

    \b
    Examples:
      ssmtree copy --dry-run /app/prod /app/staging
      ssmtree copy --yes --overwrite /app/prod /app/staging
      ssmtree copy --decrypt --kms-key-id alias/my-key /app/prod /app/staging
    """
    _validate_path(source)
    _validate_path(dest)

    try:
        params = fetch_parameters(source, decrypt=decrypt, profile=profile, region=region)
    except FetchError as exc:
        _abort(str(exc))
        return

    if not params:
        console.print(f"[yellow]No parameters found under {source}[/]")
        return

    if dry_run:
        table = render_copy_plan(params, source, dest)
        console.print(table)
        console.print(f"\n[dim]Dry run: {len(params)} parameter(s) would be copied.[/]")
        return

    if not yes:
        if overwrite:
            console.print(
                f"[bold yellow]WARNING:[/] --overwrite is enabled. "
                f"Existing parameters under {dest} will be replaced."
            )
        if not click.confirm(f"Copy {len(params)} parameter(s) to {dest}?"):
            console.print("[dim]Aborted.[/]")
            return

    session = boto3.Session(profile_name=profile, region_name=region)
    ssm_client = session.client("ssm")

    try:
        written, failed = copy_namespace(
            source_params=params,
            source_prefix=source,
            dest_prefix=dest,
            ssm_client=ssm_client,
            overwrite=overwrite,
            dry_run=False,
            kms_key_id=kms_key_id,
        )
    except CopyError as exc:
        _abort(str(exc))
        return

    console.print(f"[bold green]Copied {len(written)} parameter(s)[/] from {source} → {dest}")
    if failed:
        console.print(f"[bold red]Failed {len(failed)} parameter(s):[/]")
        for path, err in failed:
            console.print(f"  {path}: {err}")
