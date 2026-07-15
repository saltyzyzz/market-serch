from __future__ import annotations

import re
from urllib.parse import quote_plus


def parse_price(text: str | None) -> float | None:
    """Extract a numeric AUD price from free text."""
    if not text:
        return None
    cleaned = text.strip().lower()
    if cleaned in {"free", "swap", "contact", "negotiable", "n/a", "poa"}:
        return 0.0 if cleaned == "free" else None

    # Prefer the first $ amount (handles $50, AU$50, A$50)
    match = re.search(r"(?:AU|A)?\$\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if digits:
        try:
            return float(digits)
        except ValueError:
            return None
    return None


def slugify_query(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")


def encode_query(query: str) -> str:
    return quote_plus(query.strip())
