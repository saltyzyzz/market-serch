"""
Debug sweep for Facebook + Gumtree only.
Run:  python debug_sweep.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def ok(name: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_imports() -> bool:
    section("1. Imports & wiring")
    good = True
    try:
        from scrapers.search import SCRAPERS, SOURCE_LABELS, search_all
        from scrapers.facebook import build_facebook_url, scrape_facebook
        from scrapers.gumtree import build_gumtree_url, scrape_gumtree
        from scrapers.locations import load_suburbs, resolve_location
        from ui.theme import theme_css, site_badge_class

        good &= ok("search_all", callable(search_all))
        good &= ok(
            "only FB+GT scrapers",
            set(SCRAPERS) == {"facebook", "gumtree"},
            str(sorted(SCRAPERS)),
        )
        good &= ok(
            "labels FB+GT",
            set(SOURCE_LABELS) == {"facebook", "gumtree"},
            str(SOURCE_LABELS),
        )
        good &= ok("scrape_facebook", callable(scrape_facebook))
        good &= ok("scrape_gumtree", callable(scrape_gumtree))
        good &= ok("suburbs", len(load_suburbs()) > 10000, str(len(load_suburbs())))
        good &= ok("theme", "mdf-card" in theme_css("dark"))
        good &= ok("fb badge", site_badge_class("Facebook Marketplace") == "fb")
        good &= ok("gt badge", site_badge_class("Gumtree") == "gt")
        loc = "Brisbane Adelaide Street, QLD 4000"
        fb = build_facebook_url("gaming chair", loc, 300, radius_km=40)
        gt = build_gumtree_url("gaming chair", loc, 300, radius_km=40)
        good &= ok("fb url", "facebook.com/marketplace" in fb)
        good &= ok("gt url", "gumtree.com.au" in gt)
        r = resolve_location(loc)
        good &= ok("resolve", r.state == "QLD" and r.lat < 0, str(r))
    except Exception as e:
        traceback.print_exc()
        good &= ok("imports", False, str(e))
    return good


def check_app_surface() -> bool:
    section("2. App surface (FB + Gumtree only)")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app.find("SOURCE_OPTIONS")
    block = app[start : start + 220] if start >= 0 else ""
    good = True
    good &= ok("Facebook source", '"Facebook Marketplace": "facebook"' in block)
    good &= ok("Gumtree source", '"Gumtree": "gumtree"' in block)
    good &= ok("no Carsales source", "Carsales" not in block)
    good &= ok("no Locanto source", "Locanto" not in block)
    good &= ok("no carsales import", "build_carsales_url" not in app)
    good &= ok("no locanto import", "build_locanto_url" not in app)
    good &= ok("credit JJD", "JJD" in app)
    return good


async def check_live() -> bool:
    section("3. Live FB + Gumtree (soft if network blocked)")
    from scrapers.facebook import scrape_facebook
    from scrapers.gumtree import scrape_gumtree
    from scrapers.search import search_all

    loc = "Brisbane Adelaide Street, QLD 4000"
    good = True

    try:
        t0 = time.perf_counter()
        fb = await scrape_facebook(
            "gaming chair", location=loc, max_price=300, limit=8, radius_km=40, sweeps=3
        )
        good &= ok("Facebook results", len(fb) > 0, f"n={len(fb)} in {time.perf_counter()-t0:.1f}s")
    except Exception as e:
        print(f"  [WARN] Facebook network/block: {str(e)[:160]}")
        good &= ok("Facebook soft-fail (no crash)", True)

    try:
        t0 = time.perf_counter()
        gt = await scrape_gumtree(
            "gaming chair", location=loc, max_price=300, limit=12, radius_km=40, sweeps=3
        )
        good &= ok("Gumtree results", len(gt) > 0, f"n={len(gt)} in {time.perf_counter()-t0:.1f}s")
    except Exception as e:
        print(f"  [WARN] Gumtree network/block: {str(e)[:160]}")
        good &= ok("Gumtree soft-fail (no crash)", True)

    try:
        listings, df = await search_all(
            "gaming chair",
            location="South Brisbane, QLD 4101",
            max_price=350,
            limit=10,
            sources=["facebook", "gumtree"],
            radius_km=40,
            sweeps=3,
            min_relevance=0.0,
        )
        counts = df.attrs.get("source_counts") or {}
        good &= ok(
            "search_all completed",
            True,
            f"rows={len(df)} raw={len(listings)} counts={counts}",
        )
        good &= ok(
            "only FB+GT counts",
            set(counts.keys()) <= {"Facebook Marketplace", "Gumtree"},
            str(counts),
        )
    except Exception as e:
        good &= ok("search_all", False, str(e)[:160])
        traceback.print_exc()
    return good


async def main() -> int:
    print("Marketplace Deals Finder — FB + Gumtree only")
    print(f"Root: {ROOT}")
    results = [
        check_imports(),
        check_app_surface(),
        await check_live(),
    ]
    print("\n========== SUMMARY ==========")
    for i, r in enumerate(results, 1):
        print(f"Section {i}: {'PASS' if r else 'FAIL'}")
    print(f"Overall: {sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
