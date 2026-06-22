"""
ExtractorEngine: the public interface.

Wraps renderer, extractor, validator, and evaluator into one clean API — the same
shape as rag-knowledge-engine's RAGEngine, so the two siblings feel identical to use.

    PDF page → render → VLM extract → validate → (optional) evaluate

The VLM client is injected through to the Extractor, so the whole engine is testable
offline with a fake client and no API key.
"""
from typing import Dict, List, Optional, Union

from .renderer import Renderer
from .extractor import Extractor, DEFAULT_MODEL
from .validator import Validator
from .evaluator import Evaluator
from .schema import Schema, get_schema


class ExtractorEngine:
    def __init__(
        self,
        client=None,
        model: str = DEFAULT_MODEL,
        dpi: int = 200,
        tolerance: float = 0.01,
    ):
        self.renderer = Renderer(dpi=dpi)
        self.extractor = Extractor(client=client, model=model)
        self.validator = Validator(tolerance=tolerance)
        self.evaluator = Evaluator(tolerance=tolerance)

    def _resolve_schema(self, schema: Union[str, Schema]) -> Schema:
        return get_schema(schema) if isinstance(schema, str) else schema

    def extract_page(
        self,
        pdf_path: str,
        page: int,
        schema: Union[str, Schema],
        gold: Optional[Dict] = None,
    ) -> Dict:
        """
        Extract one page into validated structured JSON.

        schema: a built-in name ("income_statement", "generic_table") or a Schema.
        gold:   optional hand-labeled answer; if given, adds eval metrics.

        Returns:
          {
            page, schema, fields, parse_ok, model,
            validation: { ok, errors, warnings, checked },
            eval?: { field_accuracy, precision, recall, ... }
          }
        """
        sch = self._resolve_schema(schema)
        rendered = self.renderer.render(pdf_path, pages=[page])
        result = self.extractor.extract(rendered[0].image_bytes, sch)

        out: Dict = {
            "page": page,
            "schema": sch.name,
            "fields": result["fields"],
            "parse_ok": result["parse_ok"],
            "model": result["model"],
            "validation": self.validator.validate(result["fields"], sch),
        }
        if gold is not None:
            out["eval"] = self.evaluator.evaluate(result["fields"], gold)
        return out

    def extract_document(
        self,
        pdf_path: str,
        schema: Union[str, Schema],
        pages: Optional[List[int]] = None,
    ) -> Dict:
        """
        Extract every requested page (or all pages) with the same schema.

        Returns { document, schema, pages: [ <extract_page result>, ... ],
                  ok } where ok is True only if every page validated.
        """
        sch = self._resolve_schema(schema)
        targets = pages or list(range(1, self.renderer.page_count(pdf_path) + 1))
        page_results = [self.extract_page(pdf_path, n, sch) for n in targets]
        return {
            "document": pdf_path,
            "schema": sch.name,
            "pages": page_results,
            "ok": all(p["validation"]["ok"] for p in page_results),
        }
