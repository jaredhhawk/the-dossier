"""Tests for the shared HTML → PDF renderer."""
from pathlib import Path
import pytest

from pipeline.pdf_render import html_to_pdf


@pytest.mark.slow
def test_html_to_pdf_writes_nonempty_pdf(tmp_path: Path):
    """Real Playwright render of a tiny HTML doc produces a valid PDF file."""
    out = tmp_path / "out.pdf"
    html_to_pdf("<html><body><h1>hello</h1></body></html>", out)
    assert out.exists(), "PDF was not written"
    assert out.stat().st_size > 100, "PDF is suspiciously small"
    # PDF magic header
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF", "File is not a valid PDF"


def test_html_to_pdf_creates_parent_dir(tmp_path: Path, monkeypatch):
    """Real html_to_pdf creates nested parent dirs before invoking Playwright."""
    import pipeline.pdf_render as pr

    # sync_playwright is imported inside the function body, so patch it at the
    # source module level. We just need the mkdir line (which runs before the
    # `with` block) to execute; raising here is enough to prove we got past it.
    import playwright.sync_api as _pw_sync_api

    def fake_sync_playwright():
        raise RuntimeError("playwright stub — real render skipped")

    monkeypatch.setattr(_pw_sync_api, "sync_playwright", fake_sync_playwright)

    nested = tmp_path / "a" / "b" / "c" / "out.pdf"
    assert not nested.parent.exists()  # Sanity: dir doesn't exist before the call

    with pytest.raises(RuntimeError, match="playwright stub"):
        pr.html_to_pdf("<html></html>", nested)

    assert nested.parent.is_dir(), "Real html_to_pdf should have created the parent dir before the render attempt"
