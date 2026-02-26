"""Tests for ssmtree.models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ssmtree.models import Parameter, TreeNode


def _make_param(**kwargs) -> Parameter:
    defaults = {
        "path": "/app/prod/db/host",
        "name": "host",
        "value": "localhost",
        "type": "String",
        "version": 1,
        "last_modified": datetime(2024, 1, 1, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return Parameter(**defaults)


class TestParameter:
    def test_string_type(self):
        p = _make_param(type="String")
        assert not p.is_secure
        assert not p.is_string_list

    def test_secure_string_type(self):
        p = _make_param(type="SecureString")
        assert p.is_secure
        assert not p.is_string_list

    def test_string_list_type(self):
        p = _make_param(type="StringList")
        assert not p.is_secure
        assert p.is_string_list

    def test_fields(self):
        p = _make_param(path="/a/b/c", name="c", value="val", version=42)
        assert p.path == "/a/b/c"
        assert p.name == "c"
        assert p.value == "val"
        assert p.version == 42

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid parameter type"):
            _make_param(type="InvalidType")


class TestTreeNode:
    def test_leaf_node(self):
        node = TreeNode(name="host", path="/app/prod/db/host")
        assert node.is_leaf
        assert not node.is_namespace

    def test_namespace_node(self):
        child = TreeNode(name="host", path="/app/prod/db/host")
        node = TreeNode(name="db", path="/app/prod/db", children={"host": child})
        assert node.is_namespace
        assert not node.is_leaf

    def test_default_no_children_no_param(self):
        node = TreeNode(name="x", path="/x")
        assert node.children == {}
        assert node.parameter is None

    def test_node_with_parameter(self):
        p = _make_param()
        node = TreeNode(name="host", path="/app/prod/db/host", parameter=p)
        assert node.parameter is p
