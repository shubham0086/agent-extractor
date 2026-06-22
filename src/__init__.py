"""
agent-extractor: turn messy financial PDFs into validated, structured JSON.

The pipeline mirrors a RAG engine's clean stage split, but upstream of retrieval:

    PDF page → render → VLM extract (schema-guided) → validate → evaluate

Public entry point is ExtractorEngine. Everything below it is independently
testable and importable without the heavy deps (PyMuPDF, the VLM SDK) installed —
those are injected or lazily imported so unit tests run fully offline.
"""
from .engine import ExtractorEngine

__all__ = ["ExtractorEngine"]
