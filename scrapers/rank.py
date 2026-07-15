from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

from .models import Listing


def _sanitize_text(value: object) -> object:
    """Strip unpaired surrogates that break pandas/pyarrow UTF-8 encoding."""
    if not isinstance(value, str):
        return value
    return value.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")


def _sanitize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        out[k] = _sanitize_text(v) if isinstance(v, str) else v
    return out


def _normalize_title(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _relevance(title: str, terms: list[str]) -> float:
    if not terms:
        return 0.5
    t = (title or "").lower()
    if not t:
        return 0.0
    hits = sum(1 for term in terms if term in t)
    # Partial credit for close tokens (e.g. "iphones" vs "iphone")
    if hits == 0:
        for term in terms:
            for word in re.findall(r"[a-z0-9]+", t):
                if term in word or word in term:
                    hits += 0.5
                    break
    score = min(hits / len(terms), 1.0)
    # Bonus if full query phrase appears
    return float(score)


def _fuzzy_dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop near-duplicate titles at similar prices across sites."""
    if df.empty:
        return df
    keep_idx: list[int] = []
    seen: list[tuple[str, float | None]] = []
    for idx, row in df.iterrows():
        norm = _normalize_title(str(row.get("title") or ""))
        price = row.get("price")
        price_f = float(price) if pd.notna(price) else None
        dup = False
        for prev_title, prev_price in seen:
            sim = SequenceMatcher(None, norm, prev_title).ratio()
            price_close = False
            if price_f is None and prev_price is None:
                price_close = True
            elif price_f is not None and prev_price is not None:
                denom = max(price_f, prev_price, 1.0)
                price_close = abs(price_f - prev_price) / denom <= 0.08
            if sim >= 0.88 and price_close:
                dup = True
                break
        if not dup:
            keep_idx.append(idx)
            seen.append((norm, price_f))
    return df.loc[keep_idx]


def rank_deals(
    listings: list[Listing],
    *,
    query: str = "",
    max_price: float | None = None,
    min_price: float | None = None,
    hide_free: bool = False,
    min_relevance: float = 0.0,
) -> pd.DataFrame:
    """
    Combine listings into a ranked table.
    Score = lower price is better + title relevance to the query.
    """
    empty_cols = [
        "rank",
        "site",
        "title",
        "price",
        "price_text",
        "location",
        "link",
        "deal_score",
        "relevance",
        "distance_km",
    ]
    if not listings:
        return pd.DataFrame(columns=empty_cols)

    rows = [_sanitize_row(l.to_dict()) for l in listings]
    df = pd.DataFrame(rows)

    if "link" in df.columns:
        df = df.drop_duplicates(subset=["link"], keep="first")

    if max_price is not None:
        df = df[(df["price"].isna()) | (df["price"] <= max_price)]
    if min_price is not None:
        df = df[(df["price"].isna()) | (df["price"] >= min_price)]
    if hide_free:
        free_mask = (df["price"].fillna(-1) == 0) | (
            df["price_text"].astype(str).str.lower().str.contains("free", na=False)
        )
        df = df[~free_mask]

    terms = [t for t in re.split(r"\s+", query.lower().strip()) if len(t) > 2]
    df["relevance"] = df["title"].map(lambda t: _relevance(str(t), terms))

    # Prefer listings that match the query; keep some low-match if nothing better
    if terms and min_relevance > 0:
        matched = df[df["relevance"] >= min_relevance]
        if not matched.empty:
            df = matched

    # Soft filter: if plenty of relevant hits, drop pure noise (0 relevance)
    if terms and len(df) > 6:
        good = df[df["relevance"] > 0]
        if len(good) >= 3:
            df = good

    df = _fuzzy_dedupe(df)

    prices = df["price"].dropna()
    if len(prices) == 0:
        df["deal_score"] = (df["relevance"] * 100).round(2)
    else:
        pmin, pmax = float(prices.min()), float(prices.max())
        span = max(pmax - pmin, 1.0)

        def score(row) -> float:
            if pd.isna(row["price"]):
                price_score = 0.15  # unknown price slightly better than "very expensive"
            else:
                price_score = 1.0 - ((row["price"] - pmin) / span)
            # Free items: high price score but only if relevant
            if not pd.isna(row["price"]) and row["price"] == 0:
                price_score = 1.0
            return round(price_score * 65 + float(row["relevance"]) * 35, 2)

        df["deal_score"] = df.apply(score, axis=1)

    # Slight boost for closer listings when distance is known
    if "distance_km" in df.columns and df["distance_km"].notna().any():
        dmax = float(df["distance_km"].dropna().max() or 1.0)
        dmax = max(dmax, 1.0)

        def near_boost(row) -> float:
            if pd.isna(row.get("distance_km")):
                return 0.0
            # up to +10 points for being closest
            return round(10.0 * (1.0 - (float(row["distance_km"]) / dmax)), 2)

        df["deal_score"] = (df["deal_score"] + df.apply(near_boost, axis=1)).clip(upper=100)

    sort_cols = ["deal_score", "relevance"]
    ascending = [False, False]
    if "distance_km" in df.columns:
        sort_cols.append("distance_km")
        ascending.append(True)
    sort_cols.append("price")
    ascending.append(True)

    df = df.sort_values(
        by=sort_cols,
        ascending=ascending,
        na_position="last",
    ).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    cols = [
        "rank",
        "site",
        "title",
        "price",
        "price_text",
        "location",
        "distance_km",
        "link",
        "deal_score",
        "relevance",
        "image",
    ]
    return df[[c for c in cols if c in df.columns]]
