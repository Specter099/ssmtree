"""Data models for ssmtree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Parameter:
    """Represents a single SSM Parameter Store parameter."""

    path: str          # full SSM path, e.g. /app/prod/db/password
    name: str          # leaf segment only, e.g. "password"
    value: str         # parameter value (may be "***" if SecureString not decrypted)
    type: str          # "String" | "SecureString" | "StringList"
    version: int
    last_modified: datetime

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
