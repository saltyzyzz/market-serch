from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from .locations import resolve_location
from .models import Listing
from .utils import parse_price

_CITY_SLUGS = {
    "brisbane",
    "sydney",
    "melbourne",
    "perth",
    "adelaide",
    "canberra",
    "hobart",
    "darwin",
    "newcastle",
}


def build_facebook_url(
    query: str,
    location: str,
    max_price: float | None = None,
    radius_km: int = 50,
) -> str:
    resolved = resolve_location(location)
    hub = resolved.gumtree_region.replace(" ", "")
    city_slug = hub if hub in _CITY_SLUGS else "brisbane"
    if hub == "goldcoast":
        city_slug = "brisbane"

    q = quote_plus(query.strip())
    radius = max(1, min(int(radius_km or 50), 500))
    # Facebook Marketplace distance filter uses the same numeric steps as the AU UI (km).
    # Snap to common Marketplace steps so the filter is actually applied.
    fb_steps = [1, 2, 5, 10, 20, 40, 60, 100, 250, 500]
    radius = min(fb_steps, key=lambda s: abs(s - radius))
    url = f"https://www.facebook.com/marketplace/{city_slug}/search?query={q}"
    if max_price is not None:
        url += f"&maxPrice={int(max_price)}"
    # High-precision suburb pin + radius (km)
    url += (
        f"&latitude={resolved.lat:.6f}&longitude={resolved.lng:.6f}"
        f"&radius={radius}&exact=false"
    )
    return url


def _fetch_html(url: str) -> str:
    headers = {
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Upgrade-Insecure-Requests": "1",
    }
    last_err: Exception | None = None
    for imp in ("chrome", "chrome131", "safari17_0"):
        try:
            r = creq.get(url, impersonate=imp, timeout=40, headers=headers)
            if r.status_code >= 400:
                last_err = RuntimeError(f"Facebook HTTP {r.status_code}")
                continue
            if "marketplace_listing_title" in r.text or "/marketplace/item/" in r.text:
                return r.text
            last_err = RuntimeError("Facebook returned page without marketplace data")
        except Exception as e:
            last_err = e
    # Fall back to Playwright if HTTP fails
    return ""


async def _fetch_with_playwright(url: str, headless: bool) -> str:
    from .browser import async_playwright, new_page, open_context

    async with async_playwright() as p:
        context = await open_context(p, headless=headless, persistent=True)
        page = await new_page(context)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(2500)
            try:
                await page.wait_for_selector(
                    "a[href*='/marketplace/item/'], div[role='main']",
                    timeout=15_000,
                )
            except Exception:
                pass
            for _ in range(3):
                await page.mouse.wheel(0, 2200)
                await page.wait_for_timeout(500)
            return await page.content()
        finally:
            await context.close()


async def scrape_facebook(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    limit: int = 25,
    headless: bool = True,
    radius_km: int = 50,
    sweeps: int = 3,
) -> list[Listing]:
    """
    Search Facebook Marketplace with up to 3 sweeps to maximise unique hits:
      1) HTTP primary radius search
      2) HTTP slightly wider radius snap (next Marketplace step)
      3) Playwright render fallback if still thin
    """
    sweeps = max(1, min(int(sweeps or 3), 3))
    fetch_limit = min(max(limit * 4, limit + 20), 80)
    results: list[Listing] = []
    sweep_stats: list[dict] = []

    # Sweep 1 — primary
    url1 = build_facebook_url(query, location, max_price, radius_km=radius_km)
    html1 = _fetch_html(url1)
    if html1:
        results = _merge_unique(results, _parse_facebook_json(html1, location, fetch_limit))
        results = _merge_unique(results, _parse_facebook_html(html1, location, fetch_limit))
    sweep_stats.append({"sweep": "http_primary", "count": len(results), "url": url1})

    # Sweep 2 — next-wider FB radius step to catch border listings
    if sweeps >= 2:
        steps = [1, 2, 5, 10, 20, 40, 60, 100, 250, 500]
        r = max(1, min(int(radius_km or 50), 500))
        wider = next((s for s in steps if s > r), r)
        if wider != r:
            url2 = build_facebook_url(query, location, max_price, radius_km=wider)
            html2 = _fetch_html(url2)
            before = len(results)
            if html2:
                results = _merge_unique(
                    results, _parse_facebook_json(html2, location, fetch_limit)
                )
                results = _merge_unique(
                    results, _parse_facebook_html(html2, location, fetch_limit)
                )
            sweep_stats.append(
                {
                    "sweep": "http_wider",
                    "radius": wider,
                    "new": len(results) - before,
                    "count": len(results),
                }
            )
        else:
            sweep_stats.append({"sweep": "http_wider", "skipped": True, "count": len(results)})

    # Sweep 3 — browser render if still sparse
    if sweeps >= 3 and len(results) < max(8, limit // 2):
        try:
            html3 = await _fetch_with_playwright(url1, headless=headless)
            before = len(results)
            results = _merge_unique(
                results, _parse_facebook_json(html3, location, fetch_limit)
            )
            results = _merge_unique(
                results, _parse_facebook_html(html3, location, fetch_limit)
            )
            sweep_stats.append(
                {
                    "sweep": "playwright",
                    "new": len(results) - before,
                    "count": len(results),
                }
            )
        except Exception as e:
            sweep_stats.append({"sweep": "playwright", "error": str(e), "count": len(results)})
            if not results:
                raise RuntimeError(f"Facebook scrape failed: {e}") from e
    else:
        sweep_stats.append(
            {
                "sweep": "playwright",
                "skipped": len(results) >= max(8, limit // 2),
                "count": len(results),
            }
        )

    scrape_facebook.last_sweep_stats = sweep_stats  # type: ignore[attr-defined]

    if not results:
        raise RuntimeError(
            "No Facebook Marketplace listings found. "
            "Try again, or uncheck headless and log in once."
        )

    if max_price is not None:
        results = [r for r in results if r.price is None or r.price <= max_price]
    return results[:fetch_limit]


def _merge_unique(base: list[Listing], extra: list[Listing]) -> list[Listing]:
    seen = {r.link for r in base}
    out = list(base)
    for r in extra:
        if r.link not in seen:
            out.append(r)
            seen.add(r.link)
    return out


def _parse_facebook_json(html: str, location: str, limit: int) -> list[Listing]:
    """Extract from embedded Marketplace GraphQL/JSON blobs."""
    results: list[Listing] = []
    seen: set[str] = set()

    # Best structure observed: listing id + photo + price + title nearby
    # listing":{"__typename":"GroupCommerceProductItem","id":"915575747459530"
    for m in re.finditer(
        r'"listing":\{"__typename":"GroupCommerceProductItem","id":"(\d+)"'
        r".{0,4000}?"
        r'"listing_price":\{"formatted_amount":"((?:\\.|[^"\\])*)","amount_with_offset_in_currency":"[^"]*","amount":"([^"]+)"\}'
        r".{0,1200}?"
        r'"marketplace_listing_title":"((?:\\.|[^"\\])*)"',
        html,
        flags=re.DOTALL,
    ):
        lid, price_text, amount, title = m.group(1), m.group(2), m.group(3), m.group(4)
        title = _unescape_js(title)
        price_text = _unescape_js(price_text)
        link = f"https://www.facebook.com/marketplace/item/{lid}/"
        if link in seen:
            continue
        seen.add(link)
        price = parse_price(price_text) or parse_price(amount)
        # Window around this match for location + photo
        chunk = html[m.start() : m.end() + 500]
        # Photo usually sits right after listing id
        photo_chunk = html[m.start() : m.start() + 1800]
        img = _extract_fb_image(photo_chunk) or _extract_fb_image(chunk)
        loc = _fb_location_from_chunk(chunk, location)

        results.append(
            Listing(
                site="Facebook Marketplace",
                title=title[:200],
                price=price,
                price_text=price_text or "N/A",
                link=link,
                location=loc,
                image=img,
            )
        )
        if len(results) >= limit:
            return results

    # Alternate order: title then price (sometimes id is elsewhere)
    if len(results) < 3:
        for m in re.finditer(
            r'"marketplace_listing_title":"((?:\\.|[^"\\])*)"'
            r".{0,2500}?"
            r'"listing_price":\{"formatted_amount":"((?:\\.|[^"\\])*)","amount_with_offset_in_currency":"[^"]*","amount":"([^"]+)"\}'
            r".{0,400}?"
            r'"city":"((?:\\.|[^"\\])*)","state":"((?:\\.|[^"\\])*)"',
            html,
            flags=re.DOTALL,
        ):
            title = _unescape_js(m.group(1))
            price_text = _unescape_js(m.group(2))
            amount = m.group(3)
            loc = f"{_unescape_js(m.group(4))}, {_unescape_js(m.group(5))}"
            # try find id before title
            window = html[max(0, m.start() - 1500) : m.start()]
            id_m = re.findall(r'"id":"(\d{10,})"', window)
            lid = id_m[-1] if id_m else None
            link = (
                f"https://www.facebook.com/marketplace/item/{lid}/"
                if lid
                else build_facebook_url(title, location)
            )
            if link in seen or title in {r.title for r in results}:
                continue
            seen.add(link)
            window = html[max(0, m.start() - 1500) : m.end() + 400]
            img = _extract_fb_image(window)
            results.append(
                Listing(
                    site="Facebook Marketplace",
                    title=title[:200],
                    price=parse_price(price_text) or parse_price(amount),
                    price_text=price_text,
                    link=link,
                    location=loc or location,
                    image=img,
                )
            )
            if len(results) >= limit:
                break

    return results


def _fb_location_from_chunk(chunk: str, fallback: str) -> str:
    """Prefer fine-grained display_name (suburb) over city-only labels."""
    display = re.search(r'"display_name":"((?:\\.|[^"\\])*)"', chunk)
    if display:
        name = _unescape_js(display.group(1))
        # "Murrumba Downs, Queensland, Australia" → keep suburb + state
        parts = [p.strip() for p in name.split(",") if p.strip()]
        if parts:
            if len(parts) >= 2:
                return f"{parts[0]}, {parts[1]}"
            return parts[0]
    city_m = re.search(r'"city":"((?:\\.|[^"\\])*)"', chunk)
    state_m = re.search(r'"state":"((?:\\.|[^"\\])*)"', chunk)
    if city_m:
        loc = _unescape_js(city_m.group(1))
        if state_m:
            loc = f"{loc}, {_unescape_js(state_m.group(1))}"
        return loc
    return fallback


def _extract_fb_image(chunk: str) -> str | None:
    """Pull marketplace photo URI from a JSON snippet."""
    # primary_listing_photo → image → uri
    m = re.search(
        r'"primary_listing_photo".{0,400}?"uri"\s*:\s*"((?:\\.|[^"\\])+)"',
        chunk,
        flags=re.DOTALL,
    )
    if not m:
        m = re.search(
            r'"image"\s*:\s*\{\s*"uri"\s*:\s*"((?:\\.|[^"\\])+)"',
            chunk,
            flags=re.DOTALL,
        )
    if not m:
        m = re.search(r'(https:\\/\\/scontent[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)', chunk, re.I)
    if not m:
        m = re.search(r'(https://scontent[^"\\]+\.(?:jpg|jpeg|png|webp)[^"\\]*)', chunk, re.I)
    if not m:
        return None
    uri = _unescape_js(m.group(1)).replace("\\/", "/")
    if uri.startswith("http"):
        return uri
    return None


def _parse_facebook_html(html: str, location: str, limit: int) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        if len(results) >= limit:
            break
        href = a["href"]
        if "/marketplace/item/" not in href:
            continue
        link = urljoin("https://www.facebook.com", href.split("?")[0])
        if link in seen:
            continue
        seen.add(link)

        card = a
        for _ in range(6):
            if card.parent and card.parent.name == "div":
                card = card.parent

        text_bits = [t.strip() for t in card.stripped_strings if t.strip()]
        if not text_bits:
            continue

        price_text = "N/A"
        title = "N/A"
        loc = location
        for bit in text_bits:
            if price_text == "N/A" and ("$" in bit or bit.lower() in {"free", "sold"}):
                price_text = bit
                continue
            if title == "N/A" and len(bit) > 2 and "$" not in bit and not bit.upper().startswith("AU"):
                if re.match(r"^[A-Za-z .'\-]+,\s*[A-Z]{2,3}$", bit):
                    loc = bit
                    continue
                title = bit
                continue
            if re.match(r"^[A-Za-z .'\-]+,\s*[A-Z]{2,3}$", bit):
                loc = bit

        if title == "N/A" or title.lower() in {"log in", "sign up"}:
            continue

        img = None
        img_tag = a.find("img") or card.find("img")
        if img_tag:
            img = img_tag.get("src")

        results.append(
            Listing(
                site="Facebook Marketplace",
                title=title[:200],
                price=parse_price(price_text),
                price_text=price_text,
                link=link,
                location=loc,
                image=img,
            )
        )

    return results


def _unescape_js(s: str) -> str:
    try:
        out = bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        out = s.replace("\\/", "/").replace('\\"', '"')
    # Drop unpaired surrogates so pandas/pyarrow never chokes
    return out.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
