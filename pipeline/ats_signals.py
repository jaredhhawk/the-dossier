"""ATS-typed dispatch for post-submit confirmation detection.

Plan 2 ships Greenhouse only. Plan 3 will add Lever and Ashby to the same
dispatch table. Returns False on unknown ATS (conservative — caller writes
Unverified, user reconciles).
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse


_GREENHOUSE_URL_PATTERNS = [
    re.compile(r"/confirmation\b", re.IGNORECASE),
    re.compile(r"/applications/\d+/thanks\b", re.IGNORECASE),
    re.compile(r"[?&]application_submitted=true\b", re.IGNORECASE),
]
_GREENHOUSE_THANKYOU_TEXT = re.compile(r"thank\s*you", re.IGNORECASE)


def greenhouse_confirmed(page, timeout_seconds: int = 10) -> bool:
    """Poll for Greenhouse confirmation signal up to timeout_seconds.

    Returns True on:
    - URL match on /confirmation, /applications/N/thanks, or ?application_submitted=true
    - DOM h1 containing "thank you" (case-insensitive)
    - DOM element with [data-application-confirmation] attribute

    Returns False on timeout (conservative miss).
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        # URL check (cheap)
        try:
            url = page.url or ""
        except Exception:
            url = ""
        for pat in _GREENHOUSE_URL_PATTERNS:
            if pat.search(url):
                return True

        # DOM check: h1 with "thank you"
        try:
            h1 = page.locator("h1")
            if h1.is_visible(timeout=200):
                text = h1.text_content() or ""
                if _GREENHOUSE_THANKYOU_TEXT.search(text):
                    return True
        except Exception:
            pass

        # DOM check: data-application-confirmation attribute
        try:
            confirm = page.locator("[data-application-confirmation]")
            if confirm.is_visible(timeout=200):
                return True
        except Exception:
            pass

        time.sleep(0.5)

    return False


def detect_confirmation(page, url: str, timeout_seconds: int = 10) -> bool:
    """Dispatch on URL host. Plan 2: Greenhouse only.

    Unknown ATS returns False (caller writes Unverified). Plan 3 will add
    Lever (jobs.lever.co) and Ashby (jobs.ashbyhq.com) handlers.
    """
    host = urlparse(url).netloc.lower()
    if "greenhouse.io" in host or "boards.greenhouse.io" in host:
        return greenhouse_confirmed(page, timeout_seconds=timeout_seconds)
    return False
