"""Tests for ssmtree.differ."""

from __future__ import annotations

from datetime import UTC, datetime

from ssmtree.differ import diff_namespaces
from ssmtree.models import Parameter


def _param(path: str, value: str = "v", prefix: str = "/prod") -> Parameter:
    segments = [s for s in path.split("/") if s]
    return Parameter(
        path=path,
        name=segments[-1] if segments else path,
        value=value,
        type="String",
        version=1,
        last_modified=datetime(2024, 1, 1, tzinfo=UTC),
    )


class TestDiffNamespaces:
    def test_identical_namespaces_no_diff(self):
        p1 = [_param("/prod/db/host", "val")]
        p2 = [_param("/staging/db/host", "val")]
        added, removed, changed = diff_namespaces(p1, p2, "/prod", "/staging")
        assert added == []
        assert removed == []
        assert changed == []

    def test_added_param(self):
        p1 = [_param("/prod/db/host", "val")]
        p2 = [
            _param("/staging/db/host", "val"),
            _param("/staging/db/port", "5432"),
        ]
        added, removed, changed = diff_namespaces(p1, p2, "/prod", "/staging")
        assert len(added) == 1
        assert added[0].path == "/staging/db/port"
        assert removed == []
        assert changed == []

    def test_removed_param(self):
        p1 = [
            _param("/prod/db/host", "val"),
            _param("/prod/db/port", "5432"),
        ]
        p2 = [_param("/staging/db/host", "val")]
        added, removed, changed = diff_namespaces(p1, p2, "/prod", "/staging")
        assert added == []
        assert len(removed) == 1
        assert removed[0].path == "/prod/db/port"
        assert changed == []

    def test_changed_param(self):
        p1 = [_param("/prod/db/host", "prod-host")]
        p2 = [_param("/staging/db/host", "staging-host")]
        added, removed, changed = diff_namespaces(p1, p2, "/prod", "/staging")
        assert added == []
        assert removed == []
        assert len(changed) == 1
        old, new = changed[0]
        assert old.value == "prod-host"
        assert new.value == "staging-host"

    def test_mixed_diff(self):
        p1 = [
            _param("/prod/a", "same"),
            _param("/prod/b", "old"),
            _param("/prod/c", "only-in-prod"),
        ]
        p2 = [
            _param("/staging/a", "same"),
            _param("/staging/b", "new"),
            _param("/staging/d", "only-in-staging"),
        ]
        added, removed, changed = diff_namespaces(p1, p2, "/prod", "/staging")

        added_paths = {p.path for p in added}
        removed_paths = {p.path for p in removed}

        assert "/staging/d" in added_paths
        assert "/prod/c" in removed_paths
        assert len(changed) == 1
        old, new = changed[0]
        assert old.path == "/prod/b"
        assert new.value == "new"

    def test_empty_both_sides(self):
        added, removed, changed = diff_namespaces([], [], "/prod", "/staging")
        assert added == []
        assert removed == []
        assert changed == []

    def test_relative_key_matching(self):
        """Params match by relative path, not absolute path."""
        p1 = [_param("/long/prefix/prod/key", "v")]
        p2 = [_param("/short/staging/key", "v")]
        added, removed, changed = diff_namespaces(
            p1, p2, "/long/prefix/prod", "/short/staging"
        )
        assert added == []
        assert removed == []
        assert changed == []
