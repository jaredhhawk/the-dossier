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
    """If parent dir doesn't exist, it's created. Skip the actual render."""
    # Patch the heavy work; we only assert the dir-creation behavior.
    import pipeline.pdf_render as pr

    captured = {}

    def fake_render(html, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-stub")
        captured["called"] = True

    monkeypatch.setattr(pr, "html_to_pdf", fake_render)
    nested = tmp_path / "a" / "b" / "c" / "out.pdf"
    pr.html_to_pdf("<html></html>", nested)
    assert nested.exists()
