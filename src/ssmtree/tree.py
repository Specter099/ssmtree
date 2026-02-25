"""Build a tree structure from a flat list of SSM parameters."""

from __future__ import annotations

import fnmatch

from ssmtree.models import Parameter, TreeNode


def build_tree(parameters: list[Parameter], root_path: str = "/") -> TreeNode:
    """Build a :class:`TreeNode` tree from a flat list of parameters.

    The *root_path* becomes the root node.  Every intermediate path segment
    becomes a ``TreeNode`` with ``parameter=None`` unless a :class:`Parameter`
    exists at that exact path.

    Args:
        parameters: Flat list of SSM parameters.
        root_path: The path that forms the root of the returned tree.

    Returns:
        Root :class:`TreeNode`.  Its ``children`` contain the top-level
        segments relative to *root_path*.
    """
    root_path = root_path.rstrip("/") or "/"
    root = TreeNode(name=root_path, path=root_path)

    # Index parameters by path for O(1) lookup when setting .parameter
    param_by_path: dict[str, Parameter] = {p.path: p for p in parameters}

    for param in parameters:
        _insert(root, param, root_path, param_by_path)

    return root


def _insert(
    root: TreeNode,
    param: Parameter,
    root_path: str,
    param_by_path: dict[str, Parameter],
) -> None:
    """Insert *param* into the tree rooted at *root*."""
    path = param.path

    # Strip the root prefix to get the relative path
    if root_path == "/":
        relative = path.lstrip("/")
    else:
        if path.startswith(root_path + "/"):
            relative = path[len(root_path) + 1 :]
        elif path == root_path:
            root.parameter = param
            return
        else:
            return  # parameter is outside the root subtree

    if not relative:
        root.parameter = param
        return

    segments = relative.split("/")
    current = root
    accumulated_path = root_path.rstrip("/")

    for i, segment in enumerate(segments):
        accumulated_path = f"{accumulated_path}/{segment}"
        if segment not in current.children:
            # Create intermediate node; assign .parameter if one exists here
            node = TreeNode(
                name=segment,
                path=accumulated_path,
                parameter=param_by_path.get(accumulated_path),
            )
            current.children[segment] = node
        current = current.children[segment]


def filter_tree(root: TreeNode, pattern: str) -> TreeNode:
    """Return a new tree containing only nodes whose path matches *pattern*.

    Intermediate namespace nodes are kept if any of their descendants match.
    Uses ``fnmatch`` glob syntax (e.g. ``"*db*"``, ``"/app/*/db*"``).

    Args:
        root: The source tree root.
        pattern: Glob pattern matched against each parameter's full path.

    Returns:
        A filtered copy of *root*.  Children that don't match are excluded.
    """
    filtered = TreeNode(name=root.name, path=root.path, parameter=root.parameter)
    for name, child in root.children.items():
        filtered_child = _filter_node(child, pattern)
        if filtered_child is not None:
            filtered.children[name] = filtered_child
    return filtered


def _filter_node(node: TreeNode, pattern: str) -> TreeNode | None:
    """Recursively filter *node*.  Returns None if nothing matches."""
    # Check if this node's own parameter matches
    self_matches = node.parameter is not None and fnmatch.fnmatch(node.path, pattern)

    # Recursively filter children
    kept_children: dict[str, TreeNode] = {}
    for name, child in node.children.items():
        result = _filter_node(child, pattern)
        if result is not None:
            kept_children[name] = result

    if self_matches or kept_children:
        return TreeNode(
            name=node.name,
            path=node.path,
            children=kept_children,
            parameter=node.parameter if self_matches else None,
        )
    return None
