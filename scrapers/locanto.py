from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from .locations import resolve_location
from .models import Listing
from .utils import parse_price


def build_locanto_url(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    radius_km: int = 50,
) -> str:
    resolved = resolve_location(location)
    city = resolved.locanto_city or "brisbane"
    q = quote_plus(query.strip())
    radius = max(1, min(int(radius_km or 50), 500))
    url = f"https://www.locanto.com.au/{city}/q/?query={q}&radius={radius}"
    if max_price is not None:
        url += f"&max_price={int(max_price)}"
    return url


async def scrape_locanto(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    limit: int = 25,
    headless: bool = True,
    radius_km: int = 50,
) -> list[Listing]:
    """Search Locanto Australia classifieds."""
    url = build_locanto_url(query, location, max_price, radius_km=radius_km)
    r = creq.get(
        url,
        impersonate="safari17_0",
        timeout=30,
        headers={"Accept-Language": "en-AU,en;q=0.9"},
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Locanto HTTP {r.status_code}")

    results = _parse_locanto_html(r.text, location, limit)
    if max_price is not None:
        results = [r for r in results if r.price is None or r.price <= max_price]
    return results[:limit]


def _parse_locanto_html(html: str, location: str, limit: int) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []
    seen: set[str] = set()

    # Locanto uses various card layouts; look for ad detail links
    candidates = soup.select(
        "a[href*='/ID_'], article a[href], .bp_ad a[href], .result a[href], "
        ".cl_listing a[href], li a[href*='locanto']"
    )
    if not candidates:
        candidates = [
            a
            for a in soup.find_all("a", href=True)
            if re.search(r"/ID_\d+|/\d{6,}\.html", a["href"])
        ]

    for a in candidates:
        if len(results) >= limit:
            break
        href = a.get("href") or ""
        if not href or href.startswith("#"):
            continue
        if not re.search(r"/ID_|\.html", href):
            continue
        # Skip nav
        if any(x in href for x in ("/g/", "/login", "signup", "faq", "post")):
            continue

        link = urljoin("https://www.locanto.com.au", href.split("?")[0])
        if link in seen:
            continue

        card = a.find_parent(["article", "li", "div"]) or a
        title = a.get_text(" ", strip=True) or ""
        if not title or len(title) < 4:
            h = card.find(["h2", "h3", "h4"])
            title = h.get_text(" ", strip=True) if h else ""
        if not title or len(title) < 4:
            continue

        # Skip pure category nav labels
        if title.lower() in {"more", "next", "previous"}:
            continue

        seen.add(link)
        text = card.get_text(" ", strip=True)
        m = re.search(r"\$\s*[\d,]+(?:\.\d{2})?|AUD\s*[\d,]+", text)
        price_text = m.group(0) if m else "N/A"
        if re.search(r"\bfree\b", text, re.I) and price_text == "N/A":
            price_text = "Free"

        results.append(
            Listing(
                site="Locanto",
                title=title[:200],
                price=parse_price(price_text),
                price_text=price_text,
                link=link,
                location=location,
            )
        )

    return results
