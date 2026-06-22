#!/usr/bin/env python3
"""
extract_demo.py — the one bounded task, end to end.

Render one page of a real PDF, extract it into structured JSON with a vision model,
validate the result (required fields + financial coherence), and print everything.

    export ANTHROPIC_API_KEY=sk-ant-...
    python extract_demo.py path/to/10-K.pdf 42 income_statement

This is the proof the core works. The MCP server (src/mcp_server.py) wraps the same
engine call as a tool; the tests cover every stage offline.
"""
import json
import sys

from src import ExtractorEngine
from src.schema import BUILTINS


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python extract_demo.py <pdf> <page> [schema]")
        print(f"       schema is one of: {list(BUILTINS)} (default: income_statement)")
        return 2

    pdf_path = sys.argv[1]
    page = int(sys.argv[2])
    schema = sys.argv[3] if len(sys.argv) > 3 else "income_statement"

    engine = ExtractorEngine()  # reads ANTHROPIC_API_KEY from env
    result = engine.extract_page(pdf_path, page, schema)

    print(json.dumps(result["fields"], indent=2))
    report = result["validation"]
    print(f"\nvalidation: {'PASS' if report['ok'] else 'FAIL'}")
    for check in report["checked"]:
        print(f"  checked  {check}")
    for warn in report["warnings"]:
        print(f"  warn     {warn}")
    for err in report["errors"]:
        print(f"  ERROR    {err}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
