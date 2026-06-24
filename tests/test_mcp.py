"""MCP dispatch tests — the pure dispatch layer, offline (no mcp package needed)."""
from src.mcp_server import _dispatch, TOOLS


def test_tools_are_declared():
    names = {t["name"] for t in TOOLS}
    assert names == {"list_schemas", "extract_page", "extract_document", "info"}
    for t in TOOLS:
        # Every tool carries behaviour-hint annotations.
        ann = t["annotations"]
        for hint in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            assert hint in ann


def test_info_dispatch_is_keyless():
    out = _dispatch("info", {})
    assert out["name"] == "agent-extractor"
    assert out["version"]
    assert set(out["tools"]) == {"list_schemas", "extract_page", "extract_document", "info"}


def test_list_schemas_dispatch():
    out = _dispatch("list_schemas", {})
    assert "income_statement" in out["schemas"]
    fields = out["schemas"]["income_statement"]["fields"]
    assert any(f["name"] == "net_income" and f["required"] for f in fields)


def test_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        _dispatch("nope", {})
