"""
Renderer: turn PDF pages into page images for a vision model.

A financial filing is not text — it is a *picture* of tables, with merged cells,
footnotes, and multi-column layout. Plain text extraction (pdfplumber, read_text)
throws that structure away. So the front-end of document intelligence is: rasterise
each page to an image at a readable DPI, then hand the image to a VLM.

PyMuPDF (fitz) is imported lazily — the module imports fine without it, so the pure
logic stays unit-testable offline. Render is the only step that needs the binary.
"""
from typing import List, Optional

try:  # heavy native dep; keep the module importable without it
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - exercised via test monkeypatch
    fitz = None

DEFAULT_DPI = 200  # readable for dense financial tables without bloating tokens


class Page:
    """One rendered page: its 1-based number and PNG bytes."""

    __slots__ = ("number", "image_bytes", "width", "height")

    def __init__(self, number: int, image_bytes: bytes, width: int = 0, height: int = 0):
        self.number = number
        self.image_bytes = image_bytes
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return f"Page(number={self.number}, bytes={len(self.image_bytes)})"


class Renderer:
    def __init__(self, dpi: int = DEFAULT_DPI):
        self.dpi = dpi

    def render(self, pdf_path: str, pages: Optional[List[int]] = None) -> List[Page]:
        """
        Rasterise the requested 1-based page numbers (or all pages) to PNG.

        Returns a list of Page. Raises RuntimeError if PyMuPDF is not installed,
        with the exact install hint — a missing native dep should fail loud, not
        silently return nothing (a past scar: silent empty results hide the cause).
        """
        if fitz is None:
            raise RuntimeError(
                "PyMuPDF is required to render PDFs. Install it: pip install pymupdf"
            )

        zoom = self.dpi / 72.0  # PDF user space is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)
        out: List[Page] = []

        with fitz.open(pdf_path) as doc:
            wanted = pages or list(range(1, doc.page_count + 1))
            for n in wanted:
                if n < 1 or n > doc.page_count:
                    raise ValueError(
                        f"page {n} out of range (document has {doc.page_count} pages)"
                    )
                page = doc.load_page(n - 1)
                pix = page.get_pixmap(matrix=matrix)
                out.append(Page(n, pix.tobytes("png"), pix.width, pix.height))
        return out

    def page_count(self, pdf_path: str) -> int:
        if fitz is None:
            raise RuntimeError(
                "PyMuPDF is required to read PDFs. Install it: pip install pymupdf"
            )
        with fitz.open(pdf_path) as doc:
            return doc.page_count
