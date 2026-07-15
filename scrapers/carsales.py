"""
Carsales.com.au scraper with anti-bot workarounds.

Order of attempts:
  1) Direct HTTP (curl_cffi fingerprints) — optional proxy via CARSALES_PROXY / HTTPS_PROXY
  2) Warm Playwright session (optional; set CARSALES_USE_BROWSER=1, or use saved storage)
  3) SERP discovery fallback (DuckDuckGo HTML/Lite) for public /cars/details/ URLs

Carsales uses AWS WAF + DataDome; many networks get hard 403 on the main site.
The SERP fallback still returns real listing links + titles from search engines.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

from .locations import resolve_location
from .models import Listing
from .utils import parse_price

_STATE_NAMES = {
    "QLD": "Queensland",
    "NSW": "New South Wales",
    "VIC": "Victoria",
    "WA": "Western Australia",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "ACT": "Australian Capital Territory",
    "NT": "Northern Territory",
}

_IMPERSONATE = ("chrome131", "chrome110", "safari17_0", "firefox135")
_ROOT = Path(__file__).resolve().parent.parent
_STORAGE = _ROOT / ".browser-data-carsales" / "storage_state.json"
_DATA_DIR = _ROOT / ".browser-data-carsales"


def build_carsales_url(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    radius_km: int = 50,
    *,
    sort: str | None = None,
    offset: int = 0,
) -> str:
    """Build a Carsales search URL using their filter DSL."""
    resolved = resolve_location(location)
    keyword = re.sub(r"\s+", " ", (query or "").strip())

    clauses: list[str] = [f"Keyword.{keyword}"]
    state_name = _STATE_NAMES.get((resolved.state or "").upper())
    if state_name:
        clauses.append(f"State.{state_name}")
    if max_price is not None and max_price > 0:
        clauses.append(f"Price.range(0..{int(max_price)})")
    pc = (resolved.postcode or "").strip()
    if pc and pc.isdigit():
        radius = max(5, min(int(radius_km or 50), 500))
        clauses.append(f"(C.Postcode.{pc}.Distance.{radius}.)")

    inner = "._.".join(clauses)
    q = f"(And.{inner}.)"
    url = f"https://www.carsales.com.au/cars/?q={quote(q, safe='().*_')}"
    if sort:
        url += f"&sort={quote(sort)}"
    if offset and offset > 0:
        url += f"&offset={int(offset)}"
    return url


def _proxy_dict() -> dict | None:
    proxy = (
        os.environ.get("CARSALES_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
    )
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _fetch_http(url: str) -> str:
    headers = {
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.carsales.com.au/",
        "Cache-Control": "no-cache",
    }
    proxies = _proxy_dict()
    last_err: Exception | None = None
    for imp in _IMPERSONATE:
        try:
            r = creq.get(
                url,
                impersonate=imp,
                timeout=40,
                headers=headers,
                proxies=proxies,
            )
            if r.status_code == 403:
                last_err = RuntimeError("Carsales HTTP 403 (AWS WAF / DataDome)")
                continue
            if r.status_code >= 400:
                last_err = RuntimeError(f"Carsales HTTP {r.status_code}")
                continue
            if len(r.text) < 2000 or "access denied" in r.text[:1500].lower():
                last_err = RuntimeError("Carsales challenge/empty page")
                continue
            if "/cars/details/" in r.text or "listing" in r.text.lower():
                return r.text
            last_err = RuntimeError("Carsales page had no listings markup")
        except Exception as e:
            last_err = e
    raise RuntimeError(str(last_err or "Carsales unreachable"))


async def _fetch_playwright(url: str, headless: bool = True) -> str:
    from playwright.async_api import async_playwright

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    use_browser = os.environ.get("CARSALES_USE_BROWSER", "").strip() in {
        "1",
        "true",
        "yes",
    }
    # Default: skip slow browser on known hard-blocks unless user opts in
    # or we already have a saved storage state from a warm session.
    if not use_browser and not _STORAGE.exists() and headless:
        raise RuntimeError(
            "Skipping Playwright (set CARSALES_USE_BROWSER=1 or run warm_carsales_session.py)"
        )

    async with async_playwright() as p:
        launch_kwargs = dict(
            headless=headless and not use_browser,
            locale="en-AU",
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        proxy = os.environ.get("CARSALES_PROXY") or os.environ.get("HTTPS_PROXY")
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        try:
            if _STORAGE.exists():
                browser = await p.chromium.launch(
                    channel="chrome",
                    headless=launch_kwargs["headless"],
                    args=launch_kwargs["args"],
                    proxy=launch_kwargs.get("proxy"),
                )
                context = await browser.new_context(
                    storage_state=str(_STORAGE),
                    locale="en-AU",
                    viewport=launch_kwargs["viewport"],
                )
                context._cs_browser = browser  # type: ignore[attr-defined]
            else:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(_DATA_DIR / "profile"),
                    channel="chrome",
                    **{k: v for k, v in launch_kwargs.items() if k != "proxy"},
                    proxy=launch_kwargs.get("proxy"),
                )
        except Exception:
            browser = await p.firefox.launch(headless=launch_kwargs["headless"])
            context = await browser.new_context(locale="en-AU")
            context._cs_browser = browser  # type: ignore[attr-defined]

        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        try:
            await page.goto(
                "https://www.carsales.com.au/",
                wait_until="domcontentloaded",
                timeout=45_000,
            )
            # If user opted into browser mode, give time to pass CAPTCHA once
            if use_browser and not headless:
                await page.wait_for_timeout(25_000)
            else:
                await page.wait_for_timeout(1200)
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(3000)
            for _ in range(3):
                await page.mouse.wheel(0, 1800)
                await page.wait_for_timeout(350)
            html = await page.content()
            # Persist cookies/storage for next run
            try:
                state = await context.storage_state()
                _STORAGE.parent.mkdir(parents=True, exist_ok=True)
                _STORAGE.write_text(json.dumps(state), encoding="utf-8")
            except Exception:
                pass
            if resp and resp.status == 403:
                raise RuntimeError("Carsales blocked browser access (403)")
            if "/cars/details/" not in html and len(html) < 5000:
                raise RuntimeError("Carsales returned no listing content")
            return html
        finally:
            browser = getattr(context, "_cs_browser", None)
            await context.close()
            if browser:
                await browser.close()


def _merge(base: list[Listing], extra: list[Listing]) -> list[Listing]:
    seen = {r.link for r in base}
    out = list(base)
    for r in extra:
        if r.link not in seen:
            out.append(r)
            seen.add(r.link)
    return out


def _title_from_carsales_slug(url: str) -> str:
    m = re.search(r"/cars/details/([^/]+)/", url)
    if not m:
        return "Carsales listing"
    return m.group(1).replace("-", " ").strip().title()


def _extract_detail_urls(html: str) -> list[str]:
    links: list[str] = []
    for m in re.finditer(r"uddg=([^&\"]+)", html):
        u = unquote(m.group(1))
        if "carsales.com.au/cars/details/" in u:
            links.append(u.split("&")[0])
    for m in re.finditer(
        r"https?://(?:www\.)?carsales\.com\.au/cars/details/[^\s\"'<>&\\]+",
        html,
    ):
        links.append(m.group(0).split("&")[0])
    out: list[str] = []
    seen: set[str] = set()
    for L in links:
        L = L.rstrip(").,]")
        if L not in seen and "/cars/details/" in L:
            seen.add(L)
            out.append(L)
    return out


def _serp_get(url: str, params: dict) -> str:
    proxies = _proxy_dict()
    r = creq.get(
        url,
        params=params,
        impersonate="chrome110",
        timeout=30,
        headers={
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        proxies=proxies,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"SERP HTTP {r.status_code}")
    if "bots use DuckDuckGo" in r.text or "anomaly-modal" in r.text:
        raise RuntimeError("SERP bot challenge")
    return r.text


def _parse_serp_listings(html: str, location: str, limit: int) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []
    seen: set[str] = set()

    # Prefer structured result blocks
    blocks = soup.select(
        ".result, .web-result, .results_links_deep, .links_main, li.b_algo, .result__body"
    )
    if not blocks:
        blocks = soup.find_all("a", href=True)

    for block in blocks:
        if len(results) >= limit:
            break
        if getattr(block, "name", None) == "a":
            anchors = [block]
            text = block.get_text(" ", strip=True)
        else:
            anchors = block.find_all("a", href=True)
            text = block.get_text(" ", strip=True)

        link = None
        for a in anchors:
            href = a.get("href") or ""
            if "uddg=" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    cand = unquote(m.group(1))
                    if "carsales.com.au/cars/details/" in cand:
                        link = cand.split("&")[0]
                        break
            if "carsales.com.au/cars/details/" in href:
                link = (
                    href
                    if href.startswith("http")
                    else urljoin("https://www.carsales.com.au", href)
                )
                link = link.split("&")[0]
                break
        if not link:
            found = _extract_detail_urls(str(block))
            if found:
                link = found[0]
        if not link or link in seen:
            continue
        seen.add(link)

        title = None
        tm = re.search(r"((?:19|20)\d{2}\s+.+?)\s*-\s*Carsales", text, flags=re.I)
        if tm:
            title = tm.group(1).strip()
        if not title:
            for a in anchors:
                t = a.get_text(" ", strip=True)
                if t and "carsales" not in t.lower() and len(t) > 8:
                    title = t
                    break
        if not title:
            title = _title_from_carsales_slug(link)
        title = re.sub(r"\s+", " ", title).strip()
        if title.lower().endswith("- carsales"):
            title = title[: -len("- carsales")].strip()

        price_m = re.search(r"(?:AU\$|A\$|\$)\s*[\d,]+", text)
        price_text = price_m.group(0) if price_m else "N/A"
        loc = location
        loc_m = re.search(
            r"([A-Za-z][A-Za-z\s'-]{1,40}),\s*(QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\b",
            text,
        )
        if loc_m:
            loc = f"{loc_m.group(1).strip()}, {loc_m.group(2)}"

        results.append(
            Listing(
                site="Carsales",
                title=title[:200],
                price=parse_price(price_text),
                price_text=price_text,
                link=link.rstrip(").,]"),
                location=loc,
            )
        )

    # Absolute URL sweep
    if len(results) < 3:
        for link in _extract_detail_urls(html):
            if link in seen:
                continue
            seen.add(link)
            results.append(
                Listing(
                    site="Carsales",
                    title=_title_from_carsales_slug(link)[:200],
                    price=None,
                    price_text="N/A",
                    link=link,
                    location=location,
                )
            )
            if len(results) >= limit:
                break
    return results


def _scrape_via_serp(
    query: str,
    location: str,
    limit: int,
    sweeps: int = 3,
) -> tuple[list[Listing], list[dict]]:
    """Discover listings via search engines when carsales.com.au is blocked."""
    resolved = resolve_location(location)
    state = _STATE_NAMES.get((resolved.state or "").upper(), "")
    city = (resolved.suburb or resolved.gumtree_region or "").split()[0]

    q_base = (query or "").strip()
    query_variants = [
        f"{q_base} site:carsales.com.au/cars/details {state}".strip(),
        f"{q_base} used site:carsales.com.au/cars/details",
        f"{q_base} site:carsales.com.au/cars/details {city}".strip(),
    ][: max(1, min(sweeps, 3))]

    engines = [
        ("ddg_html", "https://html.duckduckgo.com/html/", "q"),
        ("ddg_lite", "https://lite.duckduckgo.com/lite/", "q"),
    ]

    results: list[Listing] = []
    stats: list[dict] = []

    for qi, q in enumerate(query_variants):
        got = False
        for eng_name, eng_url, param in engines:
            try:
                if qi or eng_name != "ddg_html":
                    time.sleep(1.2)
                html = _serp_get(eng_url, {param: q})
                hits = _parse_serp_listings(html, location, limit * 2)
                before = len(results)
                results = _merge(results, hits)
                stats.append(
                    {
                        "sweep": f"serp_{eng_name}_{qi+1}",
                        "query": q,
                        "page_rows": len(hits),
                        "new_unique": len(results) - before,
                        "total": len(results),
                        "mode": "serp",
                    }
                )
                if hits:
                    got = True
                    break
            except Exception as e:
                stats.append(
                    {
                        "sweep": f"serp_{eng_name}_{qi+1}",
                        "query": q,
                        "error": str(e),
                        "new_unique": 0,
                        "total": len(results),
                        "mode": "serp",
                    }
                )
        if not got:
            continue
    return results, stats


async def scrape_carsales(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    limit: int = 25,
    headless: bool = True,
    radius_km: int = 50,
    sweeps: int = 3,
) -> list[Listing]:
    """
    Search carsales.com.au with direct + SERP workarounds.
    """
    sweeps = max(1, min(int(sweeps or 3), 3))
    fetch_cap = min(max(limit * 3, 30), 80)
    results: list[Listing] = []
    sweep_stats: list[dict] = []
    last_err: Exception | None = None
    blocked = False

    specs = [
        {"name": "default", "sort": None, "offset": 0},
        {"name": "price_asc", "sort": "Price", "offset": 0},
        {"name": "offset_12", "sort": None, "offset": 12},
    ][:sweeps]

    for i, spec in enumerate(specs):
        if blocked:
            sweep_stats.append(
                {
                    "sweep": spec["name"],
                    "skipped": True,
                    "reason": "blocked",
                    "new_unique": 0,
                }
            )
            continue

        url = build_carsales_url(
            query,
            location,
            max_price=max_price,
            radius_km=radius_km,
            sort=spec.get("sort"),
            offset=int(spec.get("offset") or 0),
        )
        try:
            try:
                html = _fetch_http(url)
            except Exception as http_err:
                last_err = http_err
                err_l = str(http_err).lower()
                hard = any(
                    x in err_l for x in ("403", "waf", "datadome", "challenge", "bot")
                )
                if hard:
                    # Optional browser (warm session / explicit opt-in), then SERP
                    try:
                        html = await _fetch_playwright(url, headless=headless)
                    except Exception as pw_err:
                        last_err = pw_err
                        blocked = True
                        sweep_stats.append(
                            {
                                "sweep": spec["name"],
                                "error": str(pw_err),
                                "new_unique": 0,
                                "total": 0,
                                "mode": "direct",
                            }
                        )
                        continue
                elif i == 0:
                    html = await _fetch_playwright(url, headless=headless)
                else:
                    raise

            page_hits = _parse_carsales_html(html, location, fetch_cap)
            before = len(results)
            results = _merge(results, page_hits)
            sweep_stats.append(
                {
                    "sweep": spec["name"],
                    "url": url,
                    "page_rows": len(page_hits),
                    "new_unique": len(results) - before,
                    "total": len(results),
                    "mode": "direct",
                }
            )
        except Exception as e:
            last_err = e
            if any(x in str(e).lower() for x in ("403", "blocked", "waf", "challenge")):
                blocked = True
            sweep_stats.append(
                {
                    "sweep": spec["name"],
                    "error": str(e),
                    "new_unique": 0,
                    "total": len(results),
                    "mode": "direct",
                }
            )

    # SERP workaround when direct site fails
    if not results:
        serp_hits, serp_stats = _scrape_via_serp(
            query, location, limit=fetch_cap, sweeps=sweeps
        )
        results = _merge(results, serp_hits)
        sweep_stats.extend(serp_stats)

    scrape_carsales.last_sweep_stats = sweep_stats  # type: ignore[attr-defined]

    if not results:
        proxy_hint = (
            " Set CARSALES_PROXY=http://user:pass@host:port for a residential proxy,"
            " or run: python warm_carsales_session.py once to save a browser session."
        )
        raise RuntimeError(
            "Carsales is blocking this network (WAF/DataDome) and SERP fallback "
            "found no listings."
            + proxy_hint
            + (f" Last error: {last_err}" if last_err else "")
        )

    if max_price is not None:
        results = [r for r in results if r.price is None or r.price <= max_price]

    terms = [t for t in re.split(r"\s+", query.lower()) if len(t) > 1]
    if terms and results:
        relevant = [r for r in results if any(t in r.title.lower() for t in terms)]
        if relevant:
            results = relevant

    return results[:fetch_cap]


def _parse_carsales_html(html: str, location: str, limit: int) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        if len(results) >= limit:
            break
        href = a["href"]
        if "/cars/details/" not in href:
            continue
        link = urljoin("https://www.carsales.com.au", href.split("?")[0])
        if link in seen:
            continue
        seen.add(link)

        card = a
        for _ in range(6):
            if card.parent and card.parent.name in {"div", "article", "li", "section"}:
                card = card.parent

        title = a.get("title") or a.get_text(" ", strip=True)
        h = card.find(["h2", "h3", "h4"]) if hasattr(card, "find") else None
        if h:
            t = h.get_text(" ", strip=True)
            if t and len(t) > 4:
                title = t
        title = re.sub(r"\s+", " ", title or "").strip()
        if not title or len(title) < 4:
            title = _title_from_carsales_slug(link)
        if title.lower() in {"view", "more", "details", "enquire"}:
            continue

        text = card.get_text(" ", strip=True) if hasattr(card, "get_text") else title
        price_m = re.search(r"(?:AU\$|A\$|\$)\s*[\d,]+(?:\.\d{2})?", text)
        price_text = price_m.group(0) if price_m else "N/A"

        loc = location
        loc_m = re.search(
            r"([A-Za-z][A-Za-z\s'-]{1,40}),\s*(QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\b",
            text,
        )
        if loc_m:
            loc = f"{loc_m.group(1).strip()}, {loc_m.group(2)}"

        img = None
        img_tag = card.find("img") if hasattr(card, "find") else None
        if img_tag:
            img = img_tag.get("src") or img_tag.get("data-src")
            if img and img.startswith("//"):
                img = "https:" + img

        results.append(
            Listing(
                site="Carsales",
                title=title[:200],
                price=parse_price(price_text),
                price_text=price_text,
                link=link,
                location=loc,
                image=img if img and str(img).startswith("http") else None,
            )
        )

    return results
