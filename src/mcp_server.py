#!/usr/bin/env python3
"""
agent-extractor MCP server.

Exposes the agent-extractor engine as MCP-standard tools any Claude or GPT agent
can call. This is the Machine OS spoke that backs the `~~extractor` connector.

Transport: stdio (the standard MCP pattern — works with Claude Desktop, Claude Code,
and any MCP client). It is the console-script target (`agent-extractor`), so it is
launchable via:  uvx --from git+https://github.com/shubham0086/agent-extractor agent-extractor

Mirrors the structure of the Node spoke (mcp-agent-toolkit/src/server.js): list_tools +
call_tool handlers, results returned as JSON text. The Anthropic key is read from the
env at call time (ANTHROPIC_API_KEY), so the server boots without it and only needs it
when a tool actually extracts.

Tools:
  list_schemas        — the built-in extraction schemas and their fields
  extract_page        — extract one PDF page into validated structured JSON
  extract_document    — extract every (or selected) page with one schema
"""
import asyncio
import json
from typing import Any, Dict, List

from .engine import ExtractorEngine
from .schema import BUILTINS

# Imported lazily inside main() so unit tests never need the mcp package installed.

TOOLS = [
    {
        "name": "list_schemas",
        "description": "List the built-in extraction schemas and their fields.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "extract_page",
        "description": (
            "Extract one page of a PDF into validated structured JSON using a "
            "vision-language model. Returns fields + a validation report (required "
            "fields, type checks, and financial coherence: totals and statement "
            "identities)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string", "description": "absolute path to the PDF"},
                "page": {"type": "integer", "description": "1-based page number"},
                "schema": {
                    "type": "string",
                    "description": f"built-in schema name; one of {list(BUILTINS)}",
                },
            },
            "required": ["pdf_path", "page", "schema"],
        },
    },
    {
        "name": "extract_document",
        "description": (
            "Extract every page (or a given list of pages) of a PDF with one schema. "
            "Returns per-page results and an overall ok flag (true only if every page "
            "validated)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string"},
                "schema": {"type": "string"},
                "pages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "optional 1-based page numbers; omit for all pages",
                },
            },
            "required": ["pdf_path", "schema"],
        },
    },
]


def _dispatch(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Pure dispatch — separated from transport so it is unit-testable offline."""
    if name == "list_schemas":
        return {
            "schemas": {
                s.name: {
                    "fields": [
                        {"name": f.name, "type": f.type, "required": f.required}
                        for f in s.fields
                    ]
                }
                for s in BUILTINS.values()
            }
        }

    engine = ExtractorEngine()  # uses ANTHROPIC_API_KEY from env

    if name == "extract_page":
        return engine.extract_page(args["pdf_path"], args["page"], args["schema"])
    if name == "extract_document":
        return engine.extract_document(
            args["pdf_path"], args["schema"], pages=args.get("pages")
        )
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    """Console-script entry point: run the stdio MCP server."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types

    server = Server("agent-extractor")

    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        try:
            result = _dispatch(name, arguments or {})
            text = json.dumps(result, indent=2)
        except Exception as err:  # surface errors as tool errors, never crash the server
            text = f"Error: {err}"
        return [types.TextContent(type="text", text=text)]

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
