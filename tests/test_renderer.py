"""Renderer tests — fake PyMuPDF so no native dep or real PDF is needed."""
import types

import pytest

import src.renderer as renderer_mod
from src.renderer import Renderer


class _FakePix:
    width, height = 850, 1100

    def tobytes(self, fmt):
        assert fmt == "png"
        return b"PNGDATA"


class _FakePage:
    def get_pixmap(self, matrix=None):
        return _FakePix()


class _FakeDoc:
    page_count = 3

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def load_page(self, idx):
        assert 0 <= idx < self.page_count
        return _FakePage()


def _fake_fitz():
    return types.SimpleNamespace(Matrix=lambda a, b: "M", open=lambda p: _FakeDoc())


def test_render_selected_page(monkeypatch):
    monkeypatch.setattr(renderer_mod, "fitz", _fake_fitz())
    pages = Renderer(dpi=144).render("any.pdf", pages=[2])
    assert len(pages) == 1
    assert pages[0].number == 2
    assert pages[0].image_bytes == b"PNGDATA"
    assert pages[0].width == 850


def test_render_all_pages(monkeypatch):
    monkeypatch.setattr(renderer_mod, "fitz", _fake_fitz())
    pages = Renderer().render("any.pdf")
    assert [p.number for p in pages] == [1, 2, 3]


def test_page_out_of_range_raises(monkeypatch):
    monkeypatch.setattr(renderer_mod, "fitz", _fake_fitz())
    with pytest.raises(ValueError):
        Renderer().render("any.pdf", pages=[9])


def test_missing_pymupdf_fails_loud(monkeypatch):
    monkeypatch.setattr(renderer_mod, "fitz", None)
    with pytest.raises(RuntimeError):
        Renderer().render("any.pdf")
