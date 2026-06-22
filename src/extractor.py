"""
Extractor: page image + schema → structured JSON, via a vision-language model.

This is the core of document intelligence. The VLM *sees* the page (layout, tables,
merged cells) and returns the schema's fields as JSON. We never write OCR ourselves —
we constrain a vision model with a schema and parse its output defensively.

The VLM client is injected (dependency injection), so:
  - tests pass a fake client and run fully offline, no API key, no network;
  - production passes an Anthropic client (or any object with the same surface).

Raw model text is never fed straight to json.loads — it is run through _clean_json
first (strip code fences, slice to the outer braces). This mirrors the hard rule from
the SDLC engine: never JSON.parse raw LLM output.
"""
import base64
import json
import re
from typing import Dict, Optional

from .schema import Schema

DEFAULT_MODEL = "claude-opus-4-8-20260528"

_SYSTEM = """You are a precise financial-document extraction engine. You are shown an \
image of one page of a financial document. Extract ONLY what is visibly present.

Rules:
- Return a single JSON object matching the requested schema. No prose, no markdown.
- Numbers: digits only (strip currency symbols, commas, and parentheses). A value in \
parentheses is negative.
- If a field is not present on the page, set it to null. Never guess or infer a value \
that is not shown.
- Preserve the document's own units and currency; do not convert."""


def _clean_json(text: str) -> str:
    """Strip code fences and slice to the outermost JSON object."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start:end + 1]
    return t


class Extractor:
    def __init__(self, client=None, model: str = DEFAULT_MODEL):
        # Lazily construct a real Anthropic client only if one was not injected,
        # so importing/using this module never requires the SDK to be installed.
        if client is None:
            import os
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.client = client
        self.model = model

    def extract(self, image_bytes: bytes, schema: Schema,
                media_type: str = "image/png") -> Dict:
        """
        Send one page image + schema to the VLM and return parsed fields.

        Returns: { "fields": {...}, "model": str, "raw": str, "parse_ok": bool }
        parse_ok=False (with fields={}) when the model returned unparseable JSON,
        so the caller can route it to a failure bucket instead of crashing.
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            f"{schema.as_prompt_spec()}\n\n"
            "Extract the fields above from this page. Return JSON only."
        )

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        raw = resp.content[0].text
        try:
            fields = json.loads(_clean_json(raw))
            parse_ok = isinstance(fields, dict)
            if not parse_ok:
                fields = {}
        except (json.JSONDecodeError, ValueError):
            fields, parse_ok = {}, False

        return {"fields": fields, "model": self.model, "raw": raw, "parse_ok": parse_ok}
