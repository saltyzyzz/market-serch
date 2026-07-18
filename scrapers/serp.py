"""
Search-engine fallback when marketplaces block direct requests (403 / WAF).
Prefers Brave HTML (works more often than DDG from locked networks).
"""

from __future__ import annotations

import re
import time
from urllib.parse import unquote

from .models import Listing
from .utils import parse_price

try:
    from curl_cffi import requests as creq

    HAS_CFFI = True
except Exception:
    creq = None  # type: ignore
    HAS_CFFI = False

try:
    import requests as req_lib

    HAS_REQUESTS = True
except Exception:
    req_lib = None  # type: ignore
    HAS_REQUESTS = False


def _http_get(url: str, params: dict | None = None, timeout: int = 28) -> str:
    headers = {
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    last_err: Exception | None = None

    # Prefer plain requests first for SERP sites (more reliable TLS on some Windows setups)
    if HAS_REQUESTS and req_lib is not None:
        try:
            r = req_lib.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code < 400 and len(r.text) > 500:
                return r.text
            last_err = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last_err = e

    if HAS_CFFI and creq is not None:
        try:
            r = creq.get(
                url,
                params=params,
                timeout=timeout,
                headers=headers,
                impersonate="chrome131",
            )
            if r.status_code < 400 and len(r.text) > 500:
                return r.text
            last_err = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last_err = e

    raise RuntimeError(str(last_err or "SERP unreachable"))


def _extract_links(html: str, must_contain: str) -> list[tuple[str, str]]:
    """Return (url, title_hint) pairs."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()

    for m in re.finditer(r"uddg=([^&\"]+)", html):
        u = unquote(m.group(1)).split("&")[0].rstrip(").,]")
        if must_contain in u and u not in seen:
            seen.add(u)
            pairs.append((u, ""))

    for m in re.finditer(
        rf"https?://(?:www\.)?{re.escape(must_contain)}[^\s\"'<>&\\]*",
        html,
    ):
        u = m.group(0).split("&")[0].rstrip(").,]")
        if u not in seen:
            seen.add(u)
            pairs.append((u, ""))

    # Relative / bare domain paths in HTML
    if "gumtree.com.au" in must_contain:
        for m in re.finditer(r"(?:https?://(?:www\.)?)?gumtree\.com\.au(/[^\s\"'<>&]+)", html):
            path = m.group(1).split("&")[0]
            u = "https://www.gumtree.com.au" + path
            if u not in seen:
                seen.add(u)
                pairs.append((u, ""))

    if "facebook.com" in must_contain:
        for m in re.finditer(
            r"https?://(?:www\.)?facebook\.com/marketplace/item/\d+[^\s\"'<>&]*",
            html,
        ):
            u = m.group(0).split("?")[0]
            if u not in seen:
                seen.add(u)
                pairs.append((u, ""))

    # Try to attach nearby titles from result anchors
    title_map: dict[str, str] = {}
    for m in re.finditer(
        r'href="([^"]+)"[^>]*>([^<]{8,160})</a>',
        html,
        flags=re.I,
    ):
        href, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        if must_contain.replace("https://", "").split("/")[0] in href or (
            "gumtree" in must_contain and "gumtree" in href
        ):
            if "uddg=" in href:
                mm = re.search(r"uddg=([^&]+)", href)
                if mm:
                    href = unquote(mm.group(1)).split("&")[0]
            if href.startswith("http") and title and "http" not in title.lower():
                title_map[href.split("?")[0]] = title

    out: list[tuple[str, str]] = []
    for u, _ in pairs:
        title = title_map.get(u, "") or title_map.get(u.rstrip("/"), "")
        if not title:
            slug = u.rstrip("/").split("/")[-1]
            if slug.isdigit() and len(u.rstrip("/").split("/")) > 1:
                slug = u.rstrip("/").split("/")[-2]
            title = slug.replace("-", " ").replace("+", " ").title() or "Listing"
        for junk in (" - Gumtree", " | Gumtree", " - Facebook", " | Facebook", " | Brave Search"):
            if title.endswith(junk):
                title = title[: -len(junk)].strip()
        out.append((u, title[:200]))
    return out


def serp_listings(
    query: str,
    *,
    site_label: str,
    must_contain: str,
    site_query: str,
    location: str = "",
    limit: int = 30,
    sweeps: int = 2,
) -> tuple[list[Listing], list[dict]]:
    variants = [
        f"{query} {site_query}".strip(),
        f"{query} for sale {site_query}".strip(),
        f'"{query}" {must_contain.split("/")[0]} {location}'.strip(),
    ][: max(1, min(int(sweeps or 2), 3))]

    engines = [
        ("brave", "https://search.brave.com/search", "q"),
        ("bing", "https://www.bing.com/search", "q"),
    ]

    results: list[Listing] = []
    stats: list[dict] = []
    seen: set[str] = set()

    for i, q in enumerate(variants):
        for eng_name, eng_url, param in engines:
            try:
                if i or eng_name != "brave":
                    time.sleep(0.4)
                params: dict = {param: q}
                if eng_name == "bing":
                    params["count"] = "25"
                    params["setlang"] = "en-AU"
                html = _http_get(eng_url, params)
                pairs = _extract_links(html, must_contain)
                before = len(results)
                for link, title in pairs:
                    if link in seen:
                        continue
                    # Prefer real listing URLs for Gumtree
                    if site_label == "Gumtree":
                        is_listing = (
                            "/web/listing/" in link
                            or "/s-ad/" in link
                            or bool(re.search(r"/s-ad/\d+", link))
                        )
                        if not is_listing:
                            # keep category search hits only if nothing else yet
                            if results or "/s-" not in link:
                                if "/web/listing/" not in link and "/s-ad/" not in link:
                                    continue
                    if site_label == "Facebook Marketplace" and "/marketplace/item/" not in link:
                        continue
                    seen.add(link)
                    price_m = re.search(r"(?:AU\$|A\$|\$)\s*[\d,]+", title)
                    price_text = price_m.group(0) if price_m else "N/A"
                    results.append(
                        Listing(
                            site=site_label,
                            title=title,
                            price=parse_price(price_text),
                            price_text=price_text,
                            link=link,
                            location=location or "",
                        )
                    )
                    if len(results) >= limit:
                        break
                stats.append(
                    {
                        "sweep": f"serp_{eng_name}_{i+1}",
                        "query": q,
                        "new_unique": len(results) - before,
                        "total": len(results),
                        "mode": "serp",
                    }
                )
                if len(results) >= max(3, limit // 4):
                    return results[:limit], stats
            except Exception as e:
                stats.append(
                    {
                        "sweep": f"serp_{eng_name}_{i+1}",
                        "query": q,
                        "error": str(e),
                        "new_unique": 0,
                        "total": len(results),
                        "mode": "serp",
                    }
                )

    # Second pass: accept broader gumtree URLs if still empty
    if not results and site_label == "Gumtree":
        try:
            html = _http_get(
                "https://search.brave.com/search",
                {"q": f"{query} site:gumtree.com.au"},
            )
            pairs = _extract_links(html, "gumtree.com.au")
            for link, title in pairs:
                if link in seen:
                    continue
                if "gumtree.com.au" not in link:
                    continue
                seen.add(link)
                results.append(
                    Listing(
                        site=site_label,
                        title=title,
                        price=None,
                        price_text="N/A",
                        link=link,
                        location=location or "",
                    )
                )
                if len(results) >= limit:
                    break
            stats.append(
                {
                    "sweep": "serp_brave_broad",
                    "new_unique": len(results),
                    "total": len(results),
                    "mode": "serp",
                }
            )
        except Exception as e:
            stats.append({"sweep": "serp_brave_broad", "error": str(e), "mode": "serp"})

    return results[:limit], stats
