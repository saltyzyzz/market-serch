"""
CLI: python cli.py "gaming chair" --location Brisbane --max-price 150
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.search import search_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Facebook Marketplace + Gumtree for deals"
    )
    parser.add_argument("query", help="Item to search for")
    parser.add_argument("--location", default="Brisbane", help="City (default: Brisbane)")
    parser.add_argument(
        "--radius",
        type=int,
        default=50,
        help="Search radius in km (default: 50)",
    )
    parser.add_argument("--max-price", type=float, default=None, help="Maximum price AUD")
    parser.add_argument("--min-price", type=float, default=None, help="Minimum price AUD")
    parser.add_argument("--limit", type=int, default=15, help="Max results per site")
    parser.add_argument("--hide-free", action="store_true", help="Hide free listings")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Only keep titles that match search terms",
    )
    parser.add_argument(
        "--sources",
        default="facebook,gumtree",
        help="Comma list: facebook,gumtree",
    )
    parser.add_argument("--no-facebook", action="store_true")
    parser.add_argument("--no-gumtree", action="store_true")
    parser.add_argument(
        "--headless-fb",
        action="store_true",
        default=True,
        help="Facebook headless (default on)",
    )
    parser.add_argument("-o", "--output", default="best_deals.csv", help="CSV output path")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    sources = [s for s in sources if s in {"facebook", "gumtree"}]
    if args.no_facebook and "facebook" in sources:
        sources.remove("facebook")
    if args.no_gumtree and "gumtree" in sources:
        sources.remove("gumtree")
    if not sources:
        print("No sources selected.")
        sys.exit(1)

    print(
        f"Searching for '{args.query}' near {args.location} "
        f"within {args.radius} km on {', '.join(sources)}…"
    )
    _listings, df = asyncio.run(
        search_all(
            query=args.query,
            location=args.location,
            max_price=args.max_price,
            min_price=args.min_price,
            limit=args.limit,
            sources=sources,
            headless_fb=args.headless_fb,
            headless_gt=True,
            parallel=True,
            hide_free=args.hide_free,
            min_relevance=0.34 if args.strict else 0.0,
            radius_km=args.radius,
        )
    )

    counts = df.attrs.get("source_counts") or {}
    if counts:
        print("Counts:", counts)
    timings = df.attrs.get("source_timings") or {}
    if timings:
        print("Timings (s):", timings)
    if df.attrs.get("elapsed_sec") is not None:
        print(f"Total: {df.attrs['elapsed_sec']}s")
    for err in df.attrs.get("errors") or []:
        print(f"Warning: {err}")

    if df.empty:
        print("No results found.")
        sys.exit(0)

    display = df[["rank", "site", "title", "price_text", "link"]].copy()
    print(display.to_string(index=False))
    df.to_csv(args.output, index=False)
    print(f"\nSaved {len(df)} deals → {args.output}")


if __name__ == "__main__":
    main()
