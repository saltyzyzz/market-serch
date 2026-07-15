from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from .locations import resolve_location
from .models import GUMTREE_LOCATIONS, Listing
from .utils import parse_price, slugify_query

# Safari TLS fingerprint bypasses Gumtree's bot wall (Chrome fingerprints get 403)
_IMPERSONATE_ORDER = ("safari17_0", "safari15_5", "chrome110")

# Three complementary result sets (Gumtree page=N query often repeats page 1)
_SWEEP_SPECS = (
    {"name": "rank_p1", "page": 1, "sort": None},
    {"name": "rank_p2", "page": 2, "sort": None},
    {"name": "newest_p1", "page": 1, "sort": "date"},
)


def build_gumtree_url(
    query: str,
    location: str,
    max_price: float | None = None,
    radius_km: int = 50,
    *,
    page: int = 1,
    sort: str | None = None,
) -> str:
    """
    Correct AU search format:
      /s-{region}/{keywords}/k0l{locationId}[/page-N]
    """
    resolved = resolve_location(location)
    region = resolved.gumtree_region
    loc_id = GUMTREE_LOCATIONS.get(region, GUMTREE_LOCATIONS["brisbane"])
    loc_slug = slugify_query(region)
    keywords = quote_plus(query.strip()).replace("%20", "+")
    url = f"https://www.gumtree.com.au/s-{loc_slug}/{keywords}/k0l{loc_id}"
    if page and int(page) > 1:
        url += f"/page-{int(page)}"

    params: list[str] = []
    if max_price is not None:
        params.append(f"price=0.00__{max_price:.2f}")
    radius = max(1, min(int(radius_km or 50), 500))
    gt_steps = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250, 500]
    radius = min(gt_steps, key=lambda s: abs(s - radius))
    params.append(f"distance={radius}")
    params.append(f"search_distance={radius}")
    if sort:
        params.append(f"sort={sort}")
    if params:
        url += "?" + "&".join(params)
    return url


def _fetch_html(url: str) -> str:
    last_err: Exception | None = None
    headers = {
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Referer": "https://www.gumtree.com.au/",
    }
    for imp in _IMPERSONATE_ORDER:
        try:
            r = creq.get(url, impersonate=imp, timeout=40, headers=headers)
            if r.status_code == 403:
                last_err = RuntimeError(f"Gumtree 403 with {imp}")
                continue
            if r.status_code >= 400:
                last_err = RuntimeError(f"Gumtree HTTP {r.status_code}")
                continue
            if "access denied" in r.text[:2000].lower():
                last_err = RuntimeError("Gumtree access denied page")
                continue
            return r.text
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(
        f"Gumtree blocked or unreachable ({last_err}). "
        "Try again later or open the search URL in your browser."
    )


def _merge_listings(base: list[Listing], extra: list[Listing]) -> list[Listing]:
    seen = {r.link for r in base}
    out = list(base)
    for r in extra:
        if r.link not in seen:
            out.append(r)
            seen.add(r.link)
    return out


async def scrape_gumtree(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    limit: int = 25,
    headless: bool = True,  # unused — HTTP client is faster/more reliable
    radius_km: int = 50,
    sweeps: int = 3,
) -> list[Listing]:
    """
    Search Gumtree Australia with up to 3 complementary sweeps:
      1) relevance/rank page 1
      2) rank page 2 (/page-2 path)
      3) newest first
    Results are merged and de-duplicated by listing URL.
    """
    sweeps = max(1, min(int(sweeps or 3), 3))
    fetch_cap = min(max(limit * 4, 40), 90)
    resolved = resolve_location(location)
    fallback_loc = f"{resolved.suburb}, {resolved.state}" if resolved.state else resolved.suburb

    results: list[Listing] = []
    sweep_stats: list[dict] = []
    errors: list[str] = []

    for spec in _SWEEP_SPECS[:sweeps]:
        url = build_gumtree_url(
            query,
            location,
            max_price=max_price,
            radius_km=radius_km,
            page=int(spec["page"]),
            sort=spec.get("sort"),
        )
        try:
            html = _fetch_html(url)
            page_hits = _parse_gumtree_html(html, fallback_loc, fetch_cap)
            # Also parse full ad objects from embedded JSON (more reliable locations)
            json_hits = _parse_gumtree_json_ads(html, fallback_loc, fetch_cap)
            before = len(results)
            results = _merge_listings(results, page_hits)
            results = _merge_listings(results, json_hits)
            added = len(results) - before
            sweep_stats.append(
                {
                    "sweep": spec["name"],
                    "url": url,
                    "page_rows": len(page_hits),
                    "json_rows": len(json_hits),
                    "new_unique": added,
                    "total": len(results),
                }
            )
        except Exception as e:
            errors.append(f"{spec['name']}: {e}")
            sweep_stats.append(
                {
                    "sweep": spec["name"],
                    "url": url,
                    "error": str(e),
                    "new_unique": 0,
                    "total": len(results),
                }
            )

    if not results and errors:
        raise RuntimeError("; ".join(errors))

    if max_price is not None:
        results = [r for r in results if r.price is None or r.price <= max_price]

    # Soft relevance filter — drop obvious unrelated ads when query has real terms
    terms = [t for t in re.split(r"\s+", query.lower()) if len(t) > 2]
    if terms and results:
        relevant = [r for r in results if any(t in r.title.lower() for t in terms)]
        if relevant:
            results = relevant

    # Attach sweep metadata on a dummy attr via first listing is messy; return list only.
    # search_all can call get_last_sweep_stats if we store module-level — keep simple:
    scrape_gumtree.last_sweep_stats = sweep_stats  # type: ignore[attr-defined]
    scrape_gumtree.last_errors = errors  # type: ignore[attr-defined]

    return results[:fetch_cap]


def _parse_gumtree_html(html: str, location: str, limit: int) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []
    seen: set[str] = set()
    image_map = _gumtree_image_map(html)

    rows = soup.select(".user-ad-row-new-design")
    if not rows:
        rows = soup.select(
            "article.user-ad-row, .user-ad-collection-new-design a[href*='/web/listing/'], "
            "a[href*='/web/listing/']"
        )

    if rows and hasattr(rows[0], "select_one"):
        for row in rows:
            if len(results) >= limit:
                break
            listing = _parse_row(row, location, image_map=image_map)
            if listing and listing.link not in seen:
                seen.add(listing.link)
                results.append(listing)

    # Fallback: schema.org / anchors
    if len(results) < 5:
        for a in soup.find_all("a", href=True):
            if len(results) >= limit:
                break
            href = a["href"]
            if "/web/listing/" not in href and "/s-ad/" not in href:
                continue
            link = urljoin("https://www.gumtree.com.au", href.split("?")[0])
            if link in seen:
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 4:
                continue
            seen.add(link)
            card = a.find_parent(["article", "li", "div"]) or a
            text = card.get_text(" ", strip=True)
            price_text = _extract_price_text(card, text)
            lid = _listing_id_from_href(href)
            results.append(
                Listing(
                    site="Gumtree",
                    title=title[:200],
                    price=parse_price(price_text),
                    price_text=_clean_price_label(price_text or "N/A"),
                    link=link,
                    location=location,
                    image=image_map.get(lid) if lid else None,
                )
            )

    return results


def _parse_gumtree_json_ads(html: str, location: str, limit: int) -> list[Listing]:
    """
    Extract listings from embedded search JSON blocks:
      "id":"1343...","title":"...","priceText":"$50","location":"Rothwell",...,"mainImageUrl":"..."
    """
    results: list[Listing] = []
    seen: set[str] = set()

    # Walk each mainImageUrl and pull the surrounding ad object fields
    for m in re.finditer(r'"mainImageUrl"\s*:\s*"([^"]+)"', html):
        if len(results) >= limit:
            break
        start = max(0, m.start() - 1600)
        end = min(len(html), m.end() + 400)
        chunk = html[start:end]
        ids = re.findall(r'"id"\s*:\s*"?(\d{6,})"?', chunk)
        titles = re.findall(r'"title"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)
        prices = re.findall(r'"priceText"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)
        locs = re.findall(r'"location"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)
        areas = re.findall(r'"locationArea"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)
        states = re.findall(r'"locationState"\s*:\s*"((?:\\.|[^"\\])*)"', chunk)

        if not ids or not titles:
            continue
        lid = ids[-1]
        title = _unescape_json(titles[-1])
        if not title or len(title) < 3:
            continue
        link = f"https://www.gumtree.com.au/web/listing/ad/{lid}"
        # Prefer category-ish path if present later; ad id path redirects fine on GT
        # Try to find seo path in chunk
        path_m = re.search(rf'/web/listing/[^"/]+/{lid}', chunk)
        if path_m:
            link = urljoin("https://www.gumtree.com.au", path_m.group(0))

        if link in seen or lid in seen:
            continue
        seen.add(link)
        seen.add(lid)

        price_text = _unescape_json(prices[-1]) if prices else "N/A"
        price_text = _clean_price_label(price_text)
        loc_parts = []
        if areas:
            a = _unescape_json(areas[-1])
            if a:
                loc_parts.append(a)
        if locs:
            l = _unescape_json(locs[-1])
            if l and l not in loc_parts:
                loc_parts.append(l)
        if states:
            s = _unescape_json(states[-1])
            if s:
                loc_parts.append(s)
        loc = ", ".join(loc_parts) if loc_parts else location
        img = m.group(1).replace("\\/", "/")

        results.append(
            Listing(
                site="Gumtree",
                title=title[:200],
                price=parse_price(price_text),
                price_text=price_text or "N/A",
                link=link,
                location=loc,
                image=img if img.startswith("http") else None,
            )
        )

    return results


def _unescape_json(s: str) -> str:
    try:
        return bytes(s, "utf-8").decode("unicode_escape").replace("\\/", "/")
    except Exception:
        return s.replace("\\/", "/").replace('\\"', '"')


def _gumtree_image_map(html: str) -> dict[str, str]:
    """Map listing id → mainImageUrl from embedded search JSON."""
    out: dict[str, str] = {}
    for m in re.finditer(r'"mainImageUrl"\s*:\s*"([^"]+)"', html):
        chunk = html[max(0, m.start() - 1200) : m.start()]
        ids = re.findall(r'"id"\s*:\s*"?(\d{6,})"?', chunk)
        if not ids:
            continue
        lid = ids[-1]
        url = m.group(1).replace("\\/", "/")
        if url.startswith("http"):
            out[lid] = url
    return out


def _listing_id_from_href(href: str) -> str | None:
    m = re.search(r"/(\d{6,})(?:\?|$|/)", href or "")
    return m.group(1) if m else None


def _parse_row(row, location: str, image_map: dict[str, str] | None = None) -> Listing | None:
    href = row.get("href") if getattr(row, "name", None) == "a" else None
    if not href:
        for cand in row.find_all("a", href=True):
            if "/web/listing/" in cand["href"] or "/s-ad/" in cand["href"]:
                href = cand["href"]
                break
        if not href:
            a = row.find("a", href=True)
            href = a["href"] if a else None
    if not href:
        return None

    title_el = row.select_one(
        ".user-ad-row-new-design__title-span, .user-ad-row-new-design__title, h2, h3"
    )
    title = title_el.get_text(" ", strip=True) if title_el else ""

    price_el = row.select_one(
        ".user-ad-price-new-design__price, .user-ad-row-new-design__price, .user-ad-price"
    )
    price_text = price_el.get_text(" ", strip=True) if price_el else "N/A"

    loc_el = row.select_one(".user-ad-row-new-design__location")
    loc = loc_el.get_text(" ", strip=True) if loc_el else location

    aria = row.get("aria-label") or ""
    if aria:
        if not title:
            title = aria.split("Price:")[0].strip(" .\n")
        if price_text in {"N/A", "", None}:
            pm = re.search(r"Price:\s*(\$[\d,.]+|Free|Contact[^.]*)", aria, re.I)
            if pm:
                price_text = pm.group(1).strip()
        if loc == location:
            lm = re.search(r"Location:\s*([^.]+)", aria, re.I)
            if lm:
                loc = lm.group(1).strip()

    if not title:
        return None
    if price_text and price_text.lower().startswith("contact"):
        price_text = "N/A"
    price_text = _clean_price_label(price_text)

    link = urljoin("https://www.gumtree.com.au", href.split("?")[0])

    img = _extract_gumtree_image(row)
    if not img and image_map:
        lid = _listing_id_from_href(href) or _listing_id_from_href(str(row.get("id") or ""))
        if not lid:
            rid = str(row.get("id") or "")
            m = re.search(r"(\d{6,})", rid)
            lid = m.group(1) if m else None
        if lid:
            img = image_map.get(lid)

    return Listing(
        site="Gumtree",
        title=title[:200],
        price=parse_price(price_text),
        price_text=price_text or "N/A",
        link=link,
        location=loc or location,
        image=img,
    )


def _extract_gumtree_image(row) -> str | None:
    for img_tag in row.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            val = img_tag.get(attr)
            if val and val.startswith("http") and "placeholder" not in val.lower():
                return val
        srcset = img_tag.get("srcset") or img_tag.get("data-srcset")
        if srcset:
            first = srcset.split(",")[0].strip().split(" ")[0]
            if first.startswith("http"):
                return first
    for el in row.find_all(style=True):
        style = el.get("style") or ""
        m = re.search(r"url\(['\"]?(https?://[^'\")\s]+)", style)
        if m:
            return m.group(1)
    return None


def _clean_price_label(price_text: str) -> str:
    if not price_text or price_text == "N/A":
        return "N/A"
    m = re.search(r"(?:AU|A)?\$\s*[\d,]+(?:\.\d{1,2})?", price_text, re.I)
    if m:
        base = m.group(0).replace(" ", "")
        extra = ""
        if re.search(r"negotiable", price_text, re.I):
            extra = " neg"
        return base + extra
    if re.search(r"\bfree\b", price_text, re.I):
        return "Free"
    return price_text.strip()


def _extract_price_text(card, full_text: str) -> str:
    for node in card.find_all(string=re.compile(r"\$\s*[\d,]+")):
        s = str(node).strip()
        if s:
            return s
    match = re.search(r"\$\s*[\d,]+(?:\.\d{2})?", full_text)
    if match:
        return match.group(0)
    if re.search(r"\bfree\b", full_text, re.I):
        return "Free"
    return "N/A"
