# Agent Extractor

Turn a messy financial PDF into validated, structured JSON, and prove the numbers hold together.

Renders each page to an image, hands it to a vision-language model with a schema, and validates the result, including financial coherence checks (subtotals must sum, statement identities must hold). It is the upstream stage every RAG pipeline assumes someone else already did: PDF in, clean structured data out.

> Sibling of [rag-knowledge-engine](https://github.com/shubham0086/rag-knowledge-engine). That repo answers questions over clean text; this one *produces* the clean structured data from documents that are really pictures of tables.

## What it does

```
PDF page → render (image) → VLM extract (schema-guided) → validate → [evaluate]
                                                              ↓
                                          required fields · type coercion
                                          totals sum · statement identities
```

Four stages, each independently testable:

| Stage | File | What it does |
|-------|------|-------------|
| **Render** | `src/renderer.py` | Rasterise PDF pages to PNG at a readable DPI (PyMuPDF). A filing is a picture of tables, not text. |
| **Extract** | `src/extractor.py` | Page image + schema → JSON via a vision model. Defensive JSON parse; never `json.loads` raw output. |
| **Validate** | `src/validator.py` | Required fields, type coercion (parens = negative), and arithmetic coherence: totals and statement identities. |
| **Evaluate** | `src/evaluator.py` | Field-level accuracy / precision / recall vs a gold record, so a prompt or model change is measurable. |

## Why coherence checks

A VLM that misreads one cell rarely returns malformed JSON. It returns *plausible, wrong* numbers. Schema-shape validation can't catch that. Arithmetic can: if `gross_profit != total_revenue - cost_of_revenue`, the extraction is wrong, and you know it without a human in the loop. That free correctness signal is the difference between a demo and something you can trust on a 200-page filing.

## Quick start

**1. Install**
```bash
pip install -r requirements.txt
```

**2. Set API key**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**3. Extract one page**
```bash
python extract_demo.py path/to/10-K.pdf 42 income_statement
```

```python
from src import ExtractorEngine

engine = ExtractorEngine()
out = engine.extract_page("10-K.pdf", page=42, schema="income_statement")

print(out["fields"])          # { "total_revenue": 1000, "net_income": 300, ... }
print(out["validation"]["ok"])  # True only if every coherence check passed
```

## API reference

```python
engine = ExtractorEngine(
    client=None,                          # inject a VLM client; None → Anthropic from env
    model="claude-opus-4-8-20260528",
    dpi=200,                              # render resolution
    tolerance=0.01,                       # relative tolerance for arithmetic checks
)

# One page → validated structured JSON (+ optional eval against a gold dict)
engine.extract_page("doc.pdf", page=42, schema="income_statement", gold=None)
# {
#   "page": 42, "schema": "income_statement", "parse_ok": True,
#   "fields": { "total_revenue": 1000, "net_income": 300, ... },
#   "validation": { "ok": True, "errors": [], "warnings": [], "checked": [...] },
#   "eval": { "field_accuracy": 1.0, "precision": 1.0, "recall": 1.0 }   # if gold given
# }

# Whole document with one schema
engine.extract_document("doc.pdf", schema="generic_table", pages=[1, 2, 3])
```

Built-in schemas: `income_statement`, `generic_table`. Bring your own with `src/schema.py`'s `Schema` + `Field` (declare `totals` to get sum checks for free).

## MCP server (Machine OS spoke)

The engine is exposed as an MCP stdio server (`src/mcp_server.py`) so any MCP client (Claude Code, Claude Desktop) can call it. It backs the `~~extractor` connector in [The Machine OS](https://github.com/shubham0086/the-machine-os).

```bash
# launched by the ai-engineering-tools plugin, or directly:
uvx --from git+https://github.com/shubham0086/agent-extractor agent-extractor
```

Tools: `list_schemas`, `extract_page`, `extract_document`.

## Tests

```bash
pytest
```

24 tests. Everything external is mocked, PyMuPDF, the vision model, and the MCP transport, so the suite runs fully offline with no key and no real PDF.

```
tests/test_renderer.py   — 4 tests  (page selection, range guard, fail-loud on missing dep)
tests/test_extractor.py  — 4 tests  (JSON parse, fenced output, garbage → not-ok)
tests/test_validator.py  — 6 tests  (required, type coercion, identities, totals)
tests/test_evaluator.py  — 4 tests  (accuracy, precision, recall, gold-scoped)
tests/test_engine.py     — 3 tests  (end-to-end with stubbed renderer + fake client)
tests/test_mcp.py        — 3 tests  (tool declaration + dispatch)
```

## Design decisions

**Why a VLM, not classic OCR?** Tesseract reads characters and loses layout. A financial table's meaning lives in its structure (which number is in which column, what the row label is). A vision model sees the page and returns the *structured* fields. We never write OCR, we constrain a vision model with a schema.

**Why Python (and `uvx`), when the other Machine OS spokes are Node/`npx`?** Document processing lives in Python, PyMuPDF, Docling, pdfplumber, the transformers VLM stack. This repo is the direct sibling of the Python `rag-knowledge-engine`, and `uvx` is the Python equivalent of the spokes' `npx` launch. The hub wires it identically; only the launcher differs.

**Why dependency-inject the VLM client?** So the whole pipeline is testable offline. Tests pass a fake client; production passes an Anthropic client. No key, no network in CI.

**Why arithmetic coherence over a confidence score?** A model's self-reported confidence is just more generation. `total_revenue - cost_of_revenue == gross_profit` is ground truth. Free, deterministic, and it catches the silent single-cell misreads that sink extraction quality.

**Why fail loud on a missing native dep?** A past scar: silently returning empty results hides the cause for hours. A missing PyMuPDF raises with the exact install hint.

## Stack

- **PyMuPDF (fitz)** — PDF page rasterisation
- **Anthropic SDK** — Claude vision for schema-guided extraction
- **mcp** — stdio MCP server (the spoke transport)
- **pytest** — 24 tests, all mocked

## Related repos

- [rag-knowledge-engine](https://github.com/shubham0086/rag-knowledge-engine) — the downstream half: retrieve + rerank + ground over the structured text this produces
- [the-machine-os](https://github.com/shubham0086/the-machine-os) — the hub; this is the `~~extractor` spoke, paired with the `/document-extraction` skill
