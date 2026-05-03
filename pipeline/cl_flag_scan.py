"""CL pre-flight scanner: regex-detect placeholder/draft markers that should
not appear in a final cover letter.

Used by execute.py before each card. Warn-only — user decides proceed/skip/quit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FlagMatch:
    pattern_name: str
    matched_text: str
    context: str  # ~80 chars surrounding the match
    position: int


# Patterns. Word-boundary on [X to avoid matching legit product names like [X-Series].
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("X_PLACEHOLDER", re.compile(r"\[X[\s\]]", re.IGNORECASE)),
    ("INSERT_PLACEHOLDER", re.compile(r"\[INSERT\b", re.IGNORECASE)),
    ("FILL_IN", re.compile(r"\bfill in\b", re.IGNORECASE)),
    ("BEFORE_SENDING", re.compile(r"\bbefore\s+sending\b", re.IGNORECASE)),
]


def scan_cl_text(text: str, context_chars: int = 80) -> list[FlagMatch]:
    """Scan CL prose for placeholder/draft markers.

    Returns empty list if clean. Each match includes ~context_chars of surrounding
    text so the user can see what triggered it.
    """
    matches: list[FlagMatch] = []
    for name, regex in _PATTERNS:
        for m in regex.finditer(text):
            start = max(0, m.start() - context_chars // 2)
            end = min(len(text), m.end() + context_chars // 2)
            context = text[start:end].replace("\n", " ").strip()
            matches.append(FlagMatch(
                pattern_name=name,
                matched_text=m.group(0),
                context=context,
                position=m.start(),
            ))
    matches.sort(key=lambda f: f.position)
    return matches
