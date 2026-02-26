"""Rich-based formatters for ssmtree output."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ssmtree.models import Parameter, TreeNode

_MAX_VALUE_LEN = 60


def _truncate(value: str) -> str:
    if len(value) <= _MAX_VALUE_LEN:
        return value
    return value[:_MAX_VALUE_LEN] + "…"


_REDACTED_LABEL = "[redacted]"


def _display_value(param: Parameter, decrypt: bool) -> str:
    """Return the value to display, or the redacted placeholder for undecrypted SecureStrings."""
    if param.is_secure and not decrypt:
        return _REDACTED_LABEL
    return _truncate(param.value)


def _param_label(param: Parameter, show_values: bool, decrypt: bool = False) -> Text:
    """Build a Rich :class:`Text` label for a parameter leaf."""
    if param.is_secure:
        name_style = "bold yellow"
        type_tag = "[SecureString]"
    elif param.is_string_list:
        name_style = "bold cyan"
        type_tag = "[StringList]"
    else:
        name_style = "bold green"
        type_tag = "[String]"

    label = Text()
    label.append(param.name, style=name_style)
    label.append(f" {type_tag}", style="dim")

    if show_values:
        display = _display_value(param, decrypt)
        style = "dim red" if display == _REDACTED_LABEL else "italic"
        label.append(f"  {display}", style=style)

    return label


def _add_node(rich_tree: Tree, node: TreeNode, show_values: bool, decrypt: bool = False) -> None:
    """Recursively add *node*'s children to *rich_tree*."""
    for child in sorted(node.children.values(), key=lambda n: n.name):
        if child.is_namespace:
            # Namespace node — bold blue, may also carry a parameter
            branch_label = Text(child.name, style="bold blue")
            if child.parameter is not None and show_values:
                display = _display_value(child.parameter, decrypt)
                style = "dim red italic" if display == _REDACTED_LABEL else "dim italic"
                branch_label.append(f"  ({display})", style=style)
            branch = rich_tree.add(branch_label)
            _add_node(branch, child, show_values, decrypt)
        else:
            # Pure leaf node — must have a parameter
            if child.parameter is not None:
                rich_tree.add(_param_label(child.parameter, show_values, decrypt))
            else:
                # Orphan namespace with no param and no children (shouldn't happen)
                rich_tree.add(Text(child.name, style="dim"))


def render_tree(root: TreeNode, show_values: bool = True, decrypt: bool = False) -> Tree:
    """Render the SSM parameter tree using Rich.

    Args:
        root: Root :class:`TreeNode` (as returned by :func:`~ssmtree.tree.build_tree`).
        show_values: When *False*, parameter values are hidden entirely.
        decrypt: When *True*, SecureString values are shown as-is; when *False*,
            they are replaced with ``[redacted]``.

    Returns:
        A :class:`rich.tree.Tree` ready to be printed.
    """
    rich_root = Tree(Text(root.path, style="bold white"))

    # If root itself is a parameter, show it
    if root.parameter is not None:
        rich_root.add(_param_label(root.parameter, show_values, decrypt))

    _add_node(rich_root, root, show_values, decrypt)
    return rich_root


def render_diff(
    added: list[Parameter],
    removed: list[Parameter],
    changed: list[tuple[Parameter, Parameter]],
    path1: str,
    path2: str,
    show_values: bool = False,
    decrypt: bool = False,
) -> Table:
    """Render a diff table between two SSM namespaces.

    Args:
        added:       Parameters present in *path2* but not *path1*.
        removed:     Parameters present in *path1* but not *path2*.
        changed:     ``(old, new)`` pairs where value differs.
        path1:       Source namespace label.
        path2:       Target namespace label.
        show_values: When *False*, parameter values are hidden in the table.
        decrypt:     When *True*, SecureString values are shown as-is; when *False*,
            they are replaced with ``[redacted]``.

    Returns:
        A :class:`rich.table.Table`.
    """
    table = Table(title=f"Diff: {path1}  →  {path2}", show_lines=True)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Relative Path")
    if show_values:
        table.add_column(path1, style="red")
        table.add_column(path2, style="green")

    for param in sorted(removed, key=lambda p: p.path):
        rel = _relative(param.path, path1)
        if show_values:
            table.add_row("removed", rel, Text(_display_value(param, decrypt)), Text(""))
        else:
            table.add_row("removed", rel)

    for param in sorted(added, key=lambda p: p.path):
        rel = _relative(param.path, path2)
        if show_values:
            table.add_row("added", rel, Text(""), Text(_display_value(param, decrypt)))
        else:
            table.add_row("added", rel)

    for old, new in sorted(changed, key=lambda pair: pair[0].path):
        rel = _relative(old.path, path1)
        if show_values:
            table.add_row("changed", rel, Text(_display_value(old, decrypt)), Text(_display_value(new, decrypt)))
        else:
            table.add_row("changed", rel)

    return table


def render_copy_plan(
    source_params: list[Parameter],
    source_prefix: str,
    dest_prefix: str,
) -> Table:
    """Render a table showing what would be copied.

    Args:
        source_params: Parameters to be copied.
        source_prefix: Source namespace prefix.
        dest_prefix:   Destination namespace prefix.

    Returns:
        A :class:`rich.table.Table`.
    """
    table = Table(
        title=f"[bold]Copy plan:[/] {source_prefix}  →  {dest_prefix}",
        show_lines=False,
    )
    table.add_column("Source Path", style="cyan")
    table.add_column("Dest Path", style="green")
    table.add_column("Type", style="dim")

    for param in sorted(source_params, key=lambda p: p.path):
        dest_path = dest_prefix.rstrip("/") + "/" + _relative(param.path, source_prefix)
        table.add_row(param.path, dest_path, param.type)

    return table


def _relative(path: str, prefix: str) -> str:
    """Strip *prefix* from *path* to get the relative segment."""
    prefix = prefix.rstrip("/")
    if path.startswith(prefix + "/"):
        return path[len(prefix) + 1 :]
    return path
