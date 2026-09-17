"""Presentation helpers for Persian text (study_system_v2_2_docs/07_JALALI_ONLY.md).

Rule: the UI is Jalali/Persian only, so **user-facing prose never shows Latin
digits**. Numbers that are data stay numeric inside JSON (the frontend formats
them itself); only prose strings are converted, exactly once, at the response
boundary.
"""

from __future__ import annotations

import re
from typing import Any

from .jalali import to_persian_digits

_PERSIAN_LETTER = re.compile(r"[\u0600-\u06FF]")


def fa_text(value: str) -> str:
    """Convert digits inside Persian prose. Strings without Persian letters are untouched."""
    if not _PERSIAN_LETTER.search(value):
        return value
    return to_persian_digits(value)


def fa_text_deep(value: Any) -> Any:
    """Apply :func:`fa_text` to every string inside a JSON-like payload."""
    if isinstance(value, str):
        return fa_text(value)
    if isinstance(value, dict):
        return {key: fa_text_deep(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [fa_text_deep(item) for item in value]
    return value
