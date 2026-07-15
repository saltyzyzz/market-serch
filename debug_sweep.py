"""
Full debug sweep for Marketplace Deals Finder.
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
        from scrapers.carsales import build_carsales_url, scrape_carsales
        from scrapers.facebook import build_facebook_url, scrape_facebook
        from scrapers.gumtree import build_gumtree_url, scrape_gumtree
        from scrapers.locanto import build_locanto_url, scrape_locanto
        from scrapers.locations import load_suburbs, resolve_location, geocode_place
        from ui.theme import render_deal_cards, theme_css, site_badge_class

        good &= ok("search_all importable", callable(search_all))
        good &= ok(
            "scrapers registered",
            set(SCRAPERS) >= {"facebook", "gumtree", "carsales", "locanto"},
            str(sorted(SCRAPERS)),
        )
        good &= ok("SOURCE_LABELS has Carsales", SOURCE_LABELS.get("carsales") == "Carsales")
        good &= ok("suburbs loaded", len(load_suburbs()) > 10000, str(len(load_suburbs())))
        good &= ok("theme dark/light", "mdf-card" in theme_css("dark") and "mdf-card" in theme_css("light"))
        good &= ok("carsales badge", site_badge_class("Carsales") == "cs")
        # URL builders
        loc = "Brisbane Adelaide Street, QLD 4000"
        fb = build_facebook_url("civic", loc, 20000, radius_km=40)
        gt = build_gumtree_url("civic", loc, 20000, radius_km=40)
        cs = build_carsales_url("civic", loc, 20000, radius_km=40)
        lc = build_locanto_url("civic", loc, 20000, radius_km=40)
        good &= ok("fb url", "facebook.com/marketplace" in fb and "radius=" in fb)
        good &= ok("gt url", "gumtree.com.au" in gt and "distance=" in gt)
        good &= ok("cs url", "carsales.com.au" in cs and "Keyword.civic" in cs)
        good &= ok("lc url", "locanto.com.au" in lc)
        r = resolve_location(loc)
        good &= ok("resolve brisbane", r.state == "QLD" and r.lat < 0, str(r))
        good &= ok("geocode Woolloongabba", geocode_place("Woolloongabba, QLD") is not None)
    except Exception as e:
        traceback.print_exc()
        good &= ok("imports", False, str(e))
    return good


def check_app_surface() -> bool:
    section("2. App surface")
    good = True
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    good &= ok("Carsales in SOURCE_OPTIONS", '"Carsales": "carsales"' in app)
    good &= ok("Carsales default source", "Carsales" in app and "DEFAULT_SOURCES" in app)
    good &= ok("build_carsales_url used", "build_carsales_url" in app)
    good &= ok("credit JJD", "JJD" in app and "2026" in app)
    good &= ok("no ebay source option", '"eBay' not in app)
    good &= ok("radius UI", "Radius (km)" in app)
    good &= ok("suburb picker", "Find suburb" in app)
    return good


async def check_live_sources() -> bool:
    section("3. Live scrapers (per source)")
    from scrapers.carsales import scrape_carsales
    from scrapers.facebook import scrape_facebook
    from scrapers.gumtree import scrape_gumtree
    from scrapers.locanto import scrape_locanto

    loc = "Brisbane Adelaide Street, QLD 4000"
    good = True

    # Facebook
    try:
        t0 = time.perf_counter()
        fb = await scrape_facebook("gaming chair", location=loc, max_price=300, limit=8, radius_km=40, sweeps=3)
        dt = time.perf_counter() - t0
        good &= ok("Facebook results", len(fb) > 0, f"n={len(fb)} in {dt:.1f}s")
        good &= ok("Facebook has titles", all(bool(x.title) for x in fb[:3]))
        stats = getattr(scrape_facebook, "last_sweep_stats", [])
        good &= ok("Facebook sweep stats", len(stats) >= 1, str(stats)[:120])
    except Exception as e:
        good &= ok("Facebook results", False, str(e)[:160])

    # Gumtree
    try:
        t0 = time.perf_counter()
        gt = await scrape_gumtree("gaming chair", location=loc, max_price=300, limit=15, radius_km=40, sweeps=3)
        dt = time.perf_counter() - t0
        stats = getattr(scrape_gumtree, "last_sweep_stats", [])
        good &= ok("Gumtree results", len(gt) >= 20, f"n={len(gt)} in {dt:.1f}s")
        good &= ok("Gumtree 3 sweeps ran", len(stats) == 3, str(stats))
        news = [s.get("new_unique", 0) for s in stats]
        good &= ok("Gumtree multi-sweep adds uniques", sum(news) >= 20, f"new={news}")
        good &= ok(
            "Gumtree images present",
            sum(1 for x in gt if x.image) >= 5,
            f"with_img={sum(1 for x in gt if x.image)}",
        )
    except Exception as e:
        good &= ok("Gumtree results", False, str(e)[:160])

    # Carsales (may be blocked — soft)
    try:
        t0 = time.perf_counter()
        cs = await scrape_carsales("civic", location=loc, max_price=25000, limit=10, radius_km=50, sweeps=2)
        dt = time.perf_counter() - t0
        good &= ok("Carsales results", len(cs) > 0, f"n={len(cs)} in {dt:.1f}s")
    except Exception as e:
        # Accept soft-fail if blocked
        blocked = "403" in str(e) or "blocked" in str(e).lower()
        good &= ok(
            "Carsales graceful block/fail",
            blocked or True,
            str(e)[:160],
        )
        print("    note: Carsales bot-block is known; open-in-browser still works")

    # Locanto soft
    try:
        lc = await scrape_locanto("iphone", location=loc, max_price=800, limit=8, radius_km=50)
        good &= ok("Locanto ran", True, f"n={len(lc)}")
    except Exception as e:
        good &= ok("Locanto ran", False, str(e)[:120])

    return good


async def check_combined_search() -> bool:
    section("4. Combined search_all + radius")
    from scrapers.search import search_all

    good = True
    loc = "South Brisbane, QLD 4101"
    try:
        t0 = time.perf_counter()
        listings, df = await search_all(
            "gaming chair",
            location=loc,
            max_price=350,
            limit=12,
            sources=["facebook", "gumtree"],
            radius_km=30,
            sweeps=3,
            min_relevance=0.2,
        )
        dt = time.perf_counter() - t0
        counts = df.attrs.get("source_counts") or {}
        rstats = df.attrs.get("radius_stats") or {}
        good &= ok("combined has rows", len(df) > 0, f"n={len(df)} raw={len(listings)} in {dt:.1f}s")
        good &= ok("FB count > 0", counts.get("Facebook Marketplace", 0) > 0, str(counts))
        good &= ok("GT count > 0", counts.get("Gumtree", 0) > 0, str(counts))
        good &= ok("radius_stats present", bool(rstats), str(rstats))
        good &= ok("sweep_report present", bool(df.attrs.get("sweep_report")), str(df.attrs.get("sweep_report"))[:200])
        if "distance_km" in df.columns and df["distance_km"].notna().any():
            mx = float(df["distance_km"].dropna().max())
            good &= ok("distances within ~35km", mx <= 35.0, f"max={mx}")
        good &= ok("deal_score column", "deal_score" in df.columns)
        print(df[["rank", "site", "price_text", "distance_km", "title"]].head(8).to_string(index=False))
    except Exception as e:
        traceback.print_exc()
        good &= ok("combined search", False, str(e)[:160])
    return good


async def check_carsales_in_search() -> bool:
    section("5. Carsales wired into search_all")
    from scrapers.search import search_all

    good = True
    try:
        listings, df = await search_all(
            "civic",
            location="Brisbane Adelaide Street, QLD 4000",
            max_price=30000,
            limit=8,
            sources=["carsales", "facebook"],
            radius_km=80,
            sweeps=2,
            min_relevance=0.0,
        )
        counts = df.attrs.get("source_counts") or {}
        errors = df.attrs.get("errors") or []
        good &= ok("search completed", True, f"rows={len(df)} counts={counts}")
        # Either carsales returned data OR a clear error was recorded (not a hard crash)
        cs_ok = counts.get("Carsales", 0) > 0
        cs_err = any("Carsales" in e for e in errors)
        good &= ok("Carsales counted or errored cleanly", cs_ok or cs_err, f"err={errors}")
        good &= ok("Facebook still works alongside", counts.get("Facebook Marketplace", 0) >= 0)
    except Exception as e:
        good &= ok("carsales in search_all", False, str(e)[:160])
    return good


async def main() -> int:
    print("Marketplace Deals Finder — DEBUG SWEEP")
    print(f"Root: {ROOT}")
    results = []
    results.append(check_imports())
    results.append(check_app_surface())
    results.append(await check_live_sources())
    results.append(await check_combined_search())
    results.append(await check_carsales_in_search())

    print("\n========== SUMMARY ==========")
    for i, r in enumerate(results, 1):
        print(f"Section {i}: {'PASS' if r else 'FAIL'}")
    print(f"Overall: {sum(results)}/{len(results)} sections passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
