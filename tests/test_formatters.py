"""Tests for ssmtree.formatters."""

from __future__ import annotations

from datetime import UTC, datetime

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ssmtree.formatters import _truncate, render_copy_plan, render_diff, render_tree
from ssmtree.models import Parameter
from ssmtree.tree import build_tree


def _param(path: str, value: str = "val", type_: str = "String") -> Parameter:
    segments = [s for s in path.split("/") if s]
    return Parameter(
        path=path,
        name=segments[-1] if segments else path,
        value=value,
        type=type_,
        version=1,
        last_modified=datetime(2024, 1, 1, tzinfo=UTC),
    )


def _render_to_str(rich_obj) -> str:
    """Render a Rich renderable to a plain string."""
    console = Console(force_terminal=False, width=200)
    with console.capture() as cap:
        console.print(rich_obj)
    return cap.get()


class TestTruncate:
    def test_short_value_unchanged(self):
        assert _truncate("hello") == "hello"

    def test_exact_max_unchanged(self):
        v = "x" * 60
        assert _truncate(v) == v

    def test_long_value_truncated(self):
        v = "x" * 61
        result = _truncate(v)
        assert result.endswith("…")
        assert len(result) == 61  # 60 chars + ellipsis

    def test_empty_string(self):
        assert _truncate("") == ""


class TestRenderTree:
    def test_returns_rich_tree(self):
        params = [_param("/app/key")]
        root = build_tree(params, root_path="/app")
        result = render_tree(root)
        assert isinstance(result, Tree)

    def test_tree_contains_param_name(self):
        params = [_param("/app/key", value="myvalue")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root))
        assert "key" in output

    def test_tree_shows_value_by_default(self):
        params = [_param("/app/key", value="myvalue")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root, show_values=True))
        assert "myvalue" in output

    def test_tree_hides_value_when_requested(self):
        params = [_param("/app/key", value="myvalue")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root, show_values=False))
        assert "myvalue" not in output

    def test_secure_string_shows_redacted_without_decrypt(self):
        # Simulates the common case: API returns ciphertext when WithDecryption=False.
        # The formatter should always show [redacted] for SecureString when decrypt=False.
        params = [_param("/app/secret", value="AQICAHi+ciphertext==", type_="SecureString")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root, show_values=True, decrypt=False))
        assert "[redacted]" in output
        assert "AQICAHi+ciphertext==" not in output

    def test_secure_string_hides_value_entirely_when_show_values_false(self):
        params = [_param("/app/secret", value="AQICAHi+ciphertext==", type_="SecureString")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root, show_values=False, decrypt=False))
        assert "[redacted]" not in output
        assert "AQICAHi+ciphertext==" not in output

    def test_secure_string_shows_value_when_decrypted(self):
        params = [_param("/app/secret", value="decrypted-value", type_="SecureString")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root, show_values=True, decrypt=True))
        assert "decrypted-value" in output
        assert "[redacted]" not in output

    def test_namespace_node_appears_in_output(self):
        params = [_param("/app/db/host")]
        root = build_tree(params, root_path="/app")
        output = _render_to_str(render_tree(root))
        assert "db" in output
        assert "host" in output

    def test_empty_tree_renders(self):
        root = build_tree([], root_path="/")
        result = render_tree(root)
        assert isinstance(result, Tree)


class TestRenderDiff:
    def test_returns_table(self):
        table = render_diff([], [], [], "/a", "/b")
        assert isinstance(table, Table)

    def test_added_params_shown(self):
        added = [_param("/b/new_key", value="newval")]
        table = render_diff(added, [], [], "/a", "/b")
        output = _render_to_str(table)
        assert "added" in output
        assert "new_key" in output

    def test_removed_params_shown(self):
        removed = [_param("/a/old_key", value="oldval")]
        table = render_diff([], removed, [], "/a", "/b")
        output = _render_to_str(table)
        assert "removed" in output

    def test_changed_params_shown(self):
        old = _param("/a/key", value="old")
        new = _param("/b/key", value="new")
        table = render_diff([], [], [(old, new)], "/a", "/b")
        output = _render_to_str(table)
        assert "changed" in output

    def test_diff_hides_values_by_default(self):
        old = _param("/a/key", value="secret-old")
        new = _param("/b/key", value="secret-new")
        table = render_diff([], [], [(old, new)], "/a", "/b")
        output = _render_to_str(table)
        assert "secret-old" not in output
        assert "secret-new" not in output

    def test_diff_shows_values_when_requested(self):
        # String params — values always shown when show_values=True
        old = _param("/a/key", value="secret-old")
        new = _param("/b/key", value="secret-new")
        table = render_diff([], [], [(old, new)], "/a", "/b", show_values=True)
        output = _render_to_str(table)
        assert "secret-old" in output
        assert "secret-new" in output

    def test_diff_redacts_secure_strings_without_decrypt(self):
        # All three status types should show [redacted] for SecureString without --decrypt
        removed = _param("/a/pw", value="AQICAHiR==", type_="SecureString")
        added = _param("/b/token", value="AQICAHiA==", type_="SecureString")
        old = _param("/a/key", value="AQICAHiB==", type_="SecureString")
        new = _param("/b/key", value="AQICAHiC==", type_="SecureString")
        table = render_diff([added], [removed], [(old, new)], "/a", "/b", show_values=True, decrypt=False)
        output = _render_to_str(table)
        assert output.count("[redacted]") == 4
        assert "AQICAHiR==" not in output
        assert "AQICAHiA==" not in output
        assert "AQICAHiB==" not in output
        assert "AQICAHiC==" not in output

    def test_diff_shows_secure_string_values_when_decrypted(self):
        old = _param("/a/key", value="plaintext-old", type_="SecureString")
        new = _param("/b/key", value="plaintext-new", type_="SecureString")
        table = render_diff([], [], [(old, new)], "/a", "/b", show_values=True, decrypt=True)
        output = _render_to_str(table)
        assert "plaintext-old" in output
        assert "plaintext-new" in output
        assert "[redacted]" not in output


class TestRenderCopyPlan:
    def test_returns_table(self):
        params = [_param("/prod/key")]
        table = render_copy_plan(params, "/prod", "/staging")
        assert isinstance(table, Table)

    def test_source_and_dest_paths_shown(self):
        params = [_param("/prod/db/host")]
        table = render_copy_plan(params, "/prod", "/staging")
        output = _render_to_str(table)
        assert "/prod/db/host" in output
        assert "/staging/db/host" in output
