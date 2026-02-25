"""Diff two SSM parameter namespaces."""

from __future__ import annotations

from ssmtree.models import Parameter


def _relative(path: str, prefix: str) -> str:
    prefix = prefix.rstrip("/")
    if path.startswith(prefix + "/"):
        return path[len(prefix) + 1 :]
    return path


def diff_namespaces(
    params1: list[Parameter],
    params2: list[Parameter],
    path1: str,
    path2: str,
) -> tuple[list[Parameter], list[Parameter], list[tuple[Parameter, Parameter]]]:
    """Compare two sets of SSM parameters by their relative paths.

    Parameters are matched by their path relative to their respective prefix,
    so ``/app/prod/db/pass`` and ``/app/staging/db/pass`` compare as the same
    key ``db/pass`` when prefixes are ``/app/prod`` and ``/app/staging``.

    Args:
        params1: Parameters from the first namespace (source / "old").
        params2: Parameters from the second namespace (target / "new").
        path1:   Prefix for *params1*.
        path2:   Prefix for *params2*.

    Returns:
        A 3-tuple ``(added, removed, changed)`` where:

        * ``added``   — parameters in *params2* not present in *params1*.
        * ``removed`` — parameters in *params1* not present in *params2*.
        * ``changed`` — ``(old, new)`` pairs where the value differs.
    """
    map1: dict[str, Parameter] = {_relative(p.path, path1): p for p in params1}
    map2: dict[str, Parameter] = {_relative(p.path, path2): p for p in params2}

    keys1 = set(map1)
    keys2 = set(map2)

    removed = [map1[k] for k in sorted(keys1 - keys2)]
    added = [map2[k] for k in sorted(keys2 - keys1)]
    changed: list[tuple[Parameter, Parameter]] = [
        (map1[k], map2[k])
        for k in sorted(keys1 & keys2)
        if map1[k].value != map2[k].value
    ]

    return added, removed, changed
