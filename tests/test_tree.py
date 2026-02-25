"""Tests for ssmtree.tree."""

from __future__ import annotations

from datetime import UTC, datetime

from ssmtree.models import Parameter
from ssmtree.tree import build_tree, filter_tree


def _param(path: str, value: str = "v", type_: str = "String") -> Parameter:
    segments = [s for s in path.split("/") if s]
    return Parameter(
        path=path,
        name=segments[-1] if segments else path,
        value=value,
        type=type_,
        version=1,
        last_modified=datetime(2024, 1, 1, tzinfo=UTC),
    )


class TestBuildTree:
    def test_empty_list_returns_root(self):
        root = build_tree([], root_path="/")
        assert root.path == "/"
        assert root.children == {}

    def test_single_param_creates_path(self):
        params = [_param("/app/key")]
        root = build_tree(params, root_path="/")
        assert "app" in root.children
        assert "key" in root.children["app"].children
        assert root.children["app"].children["key"].parameter is not None

    def test_nested_params(self):
        params = [
            _param("/app/prod/db/host"),
            _param("/app/prod/db/port"),
        ]
        root = build_tree(params, root_path="/")

        db_node = root.children["app"].children["prod"].children["db"]
        assert "host" in db_node.children
        assert "port" in db_node.children

    def test_intermediate_node_without_param(self):
        params = [_param("/app/prod/key")]
        root = build_tree(params, root_path="/app")

        prod_node = root.children["prod"]
        assert prod_node.parameter is None
        assert "key" in prod_node.children

    def test_param_at_intermediate_node(self):
        """A parameter can exist at an intermediate path that also has children."""
        params = [
            _param("/app/prod"),      # intermediate path also has a parameter
            _param("/app/prod/key"),
        ]
        root = build_tree(params, root_path="/app")

        prod_node = root.children["prod"]
        assert prod_node.parameter is not None
        assert prod_node.parameter.path == "/app/prod"
        assert "key" in prod_node.children

    def test_root_path_prefix(self):
        params = [_param("/app/prod/db/host")]
        root = build_tree(params, root_path="/app/prod")

        assert "db" in root.children
        assert "host" in root.children["db"].children

    def test_node_names_are_segments(self):
        params = [_param("/x/y/z")]
        root = build_tree(params, root_path="/")

        assert root.children["x"].name == "x"
        assert root.children["x"].children["y"].name == "y"
        assert root.children["x"].children["y"].children["z"].name == "z"

    def test_sibling_params(self):
        params = [
            _param("/ns/a"),
            _param("/ns/b"),
            _param("/ns/c"),
        ]
        root = build_tree(params, root_path="/ns")
        assert set(root.children.keys()) == {"a", "b", "c"}

    def test_params_outside_root_ignored(self):
        params = [
            _param("/app/prod/key"),
            _param("/other/key"),
        ]
        root = build_tree(params, root_path="/app/prod")
        assert "app" not in root.children
        assert "other" not in root.children
        assert "key" in root.children

    def test_leaf_node_is_leaf(self):
        params = [_param("/app/key")]
        root = build_tree(params, root_path="/app")
        assert root.children["key"].is_leaf

    def test_namespace_node_is_namespace(self):
        params = [_param("/app/db/host")]
        root = build_tree(params, root_path="/app")
        assert root.children["db"].is_namespace


class TestFilterTree:
    def test_filter_matching_path(self):
        params = [
            _param("/app/prod/db/host"),
            _param("/app/prod/api/key"),
        ]
        root = build_tree(params, root_path="/app/prod")
        filtered = filter_tree(root, "*/db/*")
        assert "db" in filtered.children
        assert "api" not in filtered.children

    def test_filter_no_match_returns_empty_root(self):
        params = [_param("/app/prod/db/host")]
        root = build_tree(params, root_path="/app/prod")
        filtered = filter_tree(root, "*/nonexistent/*")
        assert filtered.children == {}

    def test_filter_glob_star(self):
        params = [
            _param("/app/prod/db_host"),
            _param("/app/prod/db_port"),
            _param("/app/prod/api_key"),
        ]
        root = build_tree(params, root_path="/app/prod")
        filtered = filter_tree(root, "*/db_*")
        child_names = set(filtered.children.keys())
        assert "db_host" in child_names
        assert "db_port" in child_names
        assert "api_key" not in child_names

    def test_filter_preserves_structure(self):
        params = [
            _param("/app/prod/db/host"),
            _param("/app/prod/db/port"),
        ]
        root = build_tree(params, root_path="/app/prod")
        filtered = filter_tree(root, "*host*")
        assert "db" in filtered.children
        assert "host" in filtered.children["db"].children
        assert "port" not in filtered.children["db"].children
