from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from .facebook import scrape_facebook
from .gumtree import scrape_gumtree
from .locations import annotate_and_filter_radius, resolve_location
from .models import Listing
from .rank import rank_deals

SCRAPERS: dict[str, Callable[..., Awaitable[list[Listing]]]] = {
    "facebook": scrape_facebook,
    "gumtree": scrape_gumtree,
}

SOURCE_LABELS = {
    "facebook": "Facebook Marketplace",
    "gumtree": "Gumtree",
}


async def search_all(
    query: str,
    location: str = "Brisbane",
    max_price: float | None = None,
    min_price: float | None = None,
    limit: int = 25,
    sources: list[str] | None = None,
    headless_fb: bool = True,
    headless_gt: bool = True,
    parallel: bool = True,
    hide_free: bool = False,
    min_relevance: float = 0.0,
    radius_km: int = 50,
    sweeps: int = 3,
) -> tuple[list[Listing], "object"]:
    """
    Run Facebook + Gumtree searches (each source does up to `sweeps` passes),
    enforce radius, and rank results.
    """
    sources = sources or ["facebook", "gumtree"]
    sources = [s for s in sources if s in SCRAPERS]
    radius_km = max(1, min(int(radius_km or 50), 500))
    sweeps = max(1, min(int(sweeps or 3), 3))
    resolved = resolve_location(location)
    t0 = time.perf_counter()

    async def run_one(name: str) -> tuple[str, list[Listing] | Exception, float, list]:
        fn = SCRAPERS[name]
        kwargs = dict(
            query=query,
            location=location,
            max_price=max_price,
            limit=limit,
            radius_km=radius_km,
            sweeps=sweeps,
            headless=headless_fb if name == "facebook" else headless_gt,
        )
        start = time.perf_counter()
        try:
            result: list[Listing] | Exception = await fn(**kwargs)
            stats = getattr(fn, "last_sweep_stats", None) or []
        except Exception as e:
            result = e
            stats = []
        return name, result, time.perf_counter() - start, stats

    if parallel and len(sources) > 1:
        results_lists = list(await asyncio.gather(*[run_one(s) for s in sources]))
    else:
        results_lists = []
        for s in sources:
            results_lists.append(await run_one(s))

    listings: list[Listing] = []
    errors: list[str] = []
    source_counts: dict[str, int] = {}
    source_timings: dict[str, float] = {}
    sweep_report: dict[str, list] = {}

    for name, item, elapsed, stats in results_lists:
        label = SOURCE_LABELS.get(name, name)
        source_timings[label] = round(elapsed, 2)
        sweep_report[label] = stats
        if isinstance(item, Exception):
            errors.append(f"{label}: {item}")
            source_counts[label] = 0
        else:
            listings.extend(item)
            source_counts[label] = len(item)

    filtered, radius_stats = annotate_and_filter_radius(
        listings,
        center_lat=resolved.lat,
        center_lng=resolved.lng,
        radius_km=radius_km,
        preferred_state=resolved.state or None,
        keep_unknown=(radius_km >= 40),
    )

    if len(filtered) < 3 and radius_stats.get("outside", 0) > 0 and radius_km < 40:
        filtered, radius_stats = annotate_and_filter_radius(
            listings,
            center_lat=resolved.lat,
            center_lng=resolved.lng,
            radius_km=radius_km,
            preferred_state=resolved.state or None,
            keep_unknown=True,
        )
        radius_stats["softened"] = True

    if len(filtered) > limit * len(sources or [1]) * 3:
        filtered = filtered[: limit * max(len(sources), 1) * 3]

    df = rank_deals(
        filtered,
        query=query,
        max_price=max_price,
        min_price=min_price,
        hide_free=hide_free,
        min_relevance=min_relevance,
    )
    df.attrs["errors"] = errors
    df.attrs["source_counts"] = source_counts
    df.attrs["source_timings"] = source_timings
    df.attrs["elapsed_sec"] = round(time.perf_counter() - t0, 2)
    df.attrs["radius_km"] = radius_km
    df.attrs["radius_stats"] = radius_stats
    df.attrs["sweep_report"] = sweep_report
    df.attrs["sweeps"] = sweeps
    df.attrs["search_centre"] = {
        "label": resolved.label,
        "lat": resolved.lat,
        "lng": resolved.lng,
        "suburb": resolved.suburb,
        "state": resolved.state,
    }
    return filtered, df
