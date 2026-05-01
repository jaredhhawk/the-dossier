"""Shared HTML → PDF renderer used by resume and cover-letter generators.

Uses Playwright's headless Chromium to render Letter-sized PDFs with
zero margin (the HTML is responsible for its own padding).
"""
from __future__ import annotations

import sys
from pathlib import Path


def html_to_pdf(html: str, output_path: Path) -> None:
    """Render HTML string to a PDF file at output_path.

    Creates the parent directory if needed. Letter format, no margins
    (HTML controls its own padding for both resume and CL templates).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "playwright required: pip install playwright "
            "&& playwright install chromium"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="Letter",
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"},
            print_background=True,
        )
        browser.close()
