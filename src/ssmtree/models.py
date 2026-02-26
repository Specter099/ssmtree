"""Data models for ssmtree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

PARAMETER_TYPES = ("String", "SecureString", "StringList")
ParameterType = Literal["String", "SecureString", "StringList"]


@dataclass
class Parameter:
    """Represents a single SSM Parameter Store parameter."""

    path: str              # full SSM path, e.g. /app/prod/db/password
    name: str              # leaf segment only, e.g. "password"
    value: str             # parameter value (may be "***" if SecureString not decrypted)
    type: ParameterType    # "String" | "SecureString" | "StringList"
    version: int
    last_modified: datetime

    def __post_init__(self) -> None:
        if self.type not in PARAMETER_TYPES:
            raise ValueError(
                f"Invalid parameter type {self.type!r}; "
                f"expected one of {PARAMETER_TYPES}"
            )

    @property
    def is_secure(self) -> bool:
        return self.type == "SecureString"

    @property
    def is_string_list(self) -> bool:
        return self.type == "StringList"


@dataclass
class TreeNode:
    """A node in the SSM parameter path tree."""

    name: str                          # display label for this path segment
    path: str                          # full path up to (and including) this segment
    children: dict[str, TreeNode] = field(default_factory=dict)
    parameter: Parameter | None = None  # set if a parameter exists at this exact path

    @property
    def is_leaf(self) -> bool:
        """True when this node has no children (pure leaf parameter node)."""
        return len(self.children) == 0

    @property
    def is_namespace(self) -> bool:
        """True when this node has children (acts as a namespace/directory)."""
        return len(self.children) > 0
