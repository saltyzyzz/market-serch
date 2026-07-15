"""Australian suburb directory + marketplace location resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd

from .models import FB_COORDS, GUMTREE_LOCATIONS

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "au_suburbs.csv"

STATES = ["All", "NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]

# Major hub centres for Gumtree region IDs / Locanto city paths
_HUBS: dict[str, tuple[float, float]] = {
    "brisbane": (-27.4698, 153.0251),
    "sydney": (-33.8688, 151.2093),
    "melbourne": (-37.8136, 144.9631),
    "perth": (-31.9505, 115.8605),
    "adelaide": (-34.9285, 138.6007),
    "gold coast": (-28.0167, 153.4000),
    "canberra": (-35.2809, 149.1300),
    "hobart": (-42.8821, 147.3272),
    "darwin": (-12.4634, 130.8456),
    "newcastle": (-32.9283, 151.7817),
}

_LOCANTO_CITY = {
    "brisbane": "brisbane",
    "sydney": "sydney",
    "melbourne": "melbourne",
    "perth": "perth",
    "adelaide": "adelaide",
    "gold coast": "gold-coast",
    "canberra": "canberra",
    "hobart": "hobart",
    "darwin": "darwin",
    "newcastle": "newcastle",
}

# Popular defaults shown at top of the suburb list
POPULAR_LABELS = [
    "Brisbane City, QLD 4000",
    "Sydney, NSW 2000",
    "Melbourne, VIC 3000",
    "Perth, WA 6000",
    "Adelaide, SA 5000",
    "Canberra, ACT 2600",
    "Hobart, TAS 7000",
    "Darwin City, NT 0800",
    "Gold Coast Mc, QLD 4217",
    "Newcastle, NSW 2300",
]


@dataclass(frozen=True)
class ResolvedLocation:
    label: str
    suburb: str
    state: str
    postcode: str
    lat: float
    lng: float
    gumtree_region: str
    locanto_city: str


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest_hub(lat: float, lng: float) -> str:
    best_name = "brisbane"
    best_d = 1e18
    for name, (hlat, hlng) in _HUBS.items():
        d = _haversine_km(lat, lng, hlat, hlng)
        if d < best_d:
            best_d = d
            best_name = name
    return best_name


@lru_cache(maxsize=1)
def load_suburbs() -> pd.DataFrame:
    if not DATA_FILE.exists():
        # Fallback to major cities only
        rows = []
        for name, (lat, lng) in FB_COORDS.items():
            rows.append(
                {
                    "suburb": name.title(),
                    "state": "",
                    "postcode": "",
                    "lat": lat,
                    "lng": lng,
                    "label": name.title(),
                }
            )
        return pd.DataFrame(rows)

    df = pd.read_csv(DATA_FILE, dtype={"postcode": str})
    df["label"] = df["label"].astype(str)
    df["suburb"] = df["suburb"].astype(str)
    df["state"] = df["state"].astype(str)
    return df


def filter_suburb_labels(
    state: str = "All",
    search: str = "",
    *,
    limit: int = 400,
) -> list[str]:
    """Return suburb labels for the UI (state + text filter)."""
    df = load_suburbs()
    if state and state != "All":
        df = df[df["state"].str.upper() == state.upper()]

    q = (search or "").strip().lower()
    if q:
        # Match suburb name or postcode
        mask = df["suburb"].str.lower().str.contains(q, na=False) | df[
            "postcode"
        ].astype(str).str.contains(q, na=False)
        # Also allow "suburb, state" fragments
        mask = mask | df["label"].str.lower().str.contains(q, na=False)
        df = df[mask]

    labels = df["label"].tolist()

    # Pin popular matches (or popular in this state) at top when no search
    if not q:
        popular = [p for p in POPULAR_LABELS if p in set(labels)]
        rest = [l for l in labels if l not in popular]
        labels = popular + rest

    return labels[:limit]


def resolve_location(location: str) -> ResolvedLocation:
    """
    Resolve a free-form location string or suburb label to coords + marketplace hubs.
    Accepts: "Paddington, QLD 4064", "Brisbane", "2000", etc.
    """
    raw = (location or "").strip()
    df = load_suburbs()

    # Exact label match
    hit = df[df["label"].str.lower() == raw.lower()]
    if hit.empty and raw:
        # Suburb only
        hit = df[df["suburb"].str.lower() == raw.lower()]
    if hit.empty and raw:
        # "Suburb, ST"
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 2:
            sub = parts[0].lower()
            st = parts[1].split()[0].upper()
            hit = df[(df["suburb"].str.lower() == sub) & (df["state"].str.upper() == st)]
    if hit.empty and raw.isdigit() and len(raw) in {3, 4}:
        pc = raw.zfill(4)
        hit = df[df["postcode"].astype(str).str.zfill(4) == pc]

    if not hit.empty:
        row = hit.iloc[0]
        lat, lng = float(row["lat"]), float(row["lng"])
        hub = nearest_hub(lat, lng)
        return ResolvedLocation(
            label=str(row["label"]),
            suburb=str(row["suburb"]),
            state=str(row["state"]),
            postcode=str(row.get("postcode") or ""),
            lat=lat,
            lng=lng,
            gumtree_region=hub if hub in GUMTREE_LOCATIONS else "brisbane",
            locanto_city=_LOCANTO_CITY.get(hub, "brisbane"),
        )

    # Legacy major-city name
    key = raw.lower().replace(" city", "").strip()
    if key in FB_COORDS:
        lat, lng = FB_COORDS[key]
        hub = key if key in GUMTREE_LOCATIONS else nearest_hub(lat, lng)
        return ResolvedLocation(
            label=raw.title() if raw else "Brisbane",
            suburb=raw.title() if raw else "Brisbane",
            state="",
            postcode="",
            lat=lat,
            lng=lng,
            gumtree_region=hub if hub in GUMTREE_LOCATIONS else "brisbane",
            locanto_city=_LOCANTO_CITY.get(hub, "brisbane"),
        )

    # Default Brisbane CBD
    lat, lng = FB_COORDS["brisbane"]
    return ResolvedLocation(
        label="Brisbane",
        suburb="Brisbane",
        state="QLD",
        postcode="4000",
        lat=lat,
        lng=lng,
        gumtree_region="brisbane",
        locanto_city="brisbane",
    )


@lru_cache(maxsize=1)
def _suburb_lookup() -> dict[str, list[tuple[str, float, float, str]]]:
    """suburb_lower -> list of (state, lat, lng, postcode)."""
    df = load_suburbs()
    idx: dict[str, list[tuple[str, float, float, str]]] = {}
    for _, row in df.iterrows():
        key = str(row["suburb"]).strip().lower()
        if not key:
            continue
        idx.setdefault(key, []).append(
            (
                str(row.get("state") or "").upper(),
                float(row["lat"]),
                float(row["lng"]),
                str(row.get("postcode") or ""),
            )
        )
    return idx


_STATE_ALIASES = {
    "qld": "QLD",
    "queensland": "QLD",
    "nsw": "NSW",
    "new south wales": "NSW",
    "vic": "VIC",
    "victoria": "VIC",
    "wa": "WA",
    "western australia": "WA",
    "sa": "SA",
    "south australia": "SA",
    "tas": "TAS",
    "tasmania": "TAS",
    "act": "ACT",
    "australian capital territory": "ACT",
    "nt": "NT",
    "northern territory": "NT",
}


def _extract_state(text: str) -> str | None:
    t = (text or "").lower()
    # Prefer explicit ", QLD" style
    import re

    m = re.search(r",\s*([a-z]{2,3})\b", t)
    if m:
        code = m.group(1).upper()
        if code in {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}:
            return code
    for alias, code in _STATE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", t):
            return code
    return None


def geocode_place(
    place_text: str,
    preferred_state: str | None = None,
) -> tuple[float, float] | None:
    """
    Best-effort geocode of a listing location string against the suburb DB.
    Examples: "Rothwell", "Brisbane, QLD", "Murrumba Downs, Queensland".
    """
    import re

    text = (place_text or "").strip()
    if not text:
        return None

    state = _extract_state(text) or (
        preferred_state.upper() if preferred_state else None
    )
    idx = _suburb_lookup()

    # Candidate place names: full string, before comma, after "Area," etc.
    candidates: list[str] = []
    cleaned = re.sub(r"\b(area|region|city|mc|bc|dc)\b", " ", text, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    candidates.append(cleaned)
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        candidates.extend(parts)
        # "Redcliffe Area, Rothwell" → prefer last local part before state
        for p in reversed(parts):
            if p.upper() not in {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"} and len(
                p
            ) > 2:
                candidates.insert(0, p)

    # Unique preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        key = c.lower().strip()
        # drop state-only tokens
        if key in _STATE_ALIASES or key.upper() in {
            "NSW",
            "VIC",
            "QLD",
            "WA",
            "SA",
            "TAS",
            "ACT",
            "NT",
            "AUSTRALIA",
            "QUEENSLAND",
        }:
            continue
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)

    for name in ordered:
        entries = idx.get(name)
        if not entries:
            # fuzzy: startswith for multi-word
            for k, ents in idx.items():
                if k.startswith(name) or name.startswith(k):
                    if abs(len(k) - len(name)) <= 4:
                        entries = ents
                        break
        if not entries:
            continue
        if state:
            for st, lat, lng, _pc in entries:
                if st == state:
                    return lat, lng
        # no state preference — first entry
        return entries[0][1], entries[0][2]

    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return _haversine_km(lat1, lng1, lat2, lng2)


def annotate_and_filter_radius(
    listings: list,
    *,
    center_lat: float,
    center_lng: float,
    radius_km: float,
    preferred_state: str | None = None,
    keep_unknown: bool | None = None,
) -> tuple[list, dict]:
    """
    Geocode each listing's location and keep those within radius_km of the centre.
    Returns (filtered_listings, stats).
    """
    radius_km = float(radius_km)
    # Small slack for suburb centroid vs actual pin (~2–3 km typical error)
    limit = radius_km + max(2.0, radius_km * 0.08)
    if keep_unknown is None:
        # Tight radius: drop unknown places so results stay local
        keep_unknown = radius_km >= 40

    kept = []
    stats = {
        "input": len(listings),
        "geocoded": 0,
        "within": 0,
        "outside": 0,
        "unknown": 0,
        "kept_unknown": 0,
        "radius_km": radius_km,
        "effective_limit_km": round(limit, 1),
    }

    for item in listings:
        loc_text = getattr(item, "location", "") or ""
        coords = geocode_place(loc_text, preferred_state=preferred_state)
        if coords is None:
            stats["unknown"] += 1
            item.distance_km = None
            item.lat = None
            item.lng = None
            if keep_unknown:
                stats["kept_unknown"] += 1
                kept.append(item)
            continue

        lat, lng = coords
        stats["geocoded"] += 1
        dist = haversine_km(center_lat, center_lng, lat, lng)
        item.lat = lat
        item.lng = lng
        item.distance_km = round(dist, 1)
        if dist <= limit:
            stats["within"] += 1
            kept.append(item)
        else:
            stats["outside"] += 1

    # Prefer closer listings first before ranking
    kept.sort(
        key=lambda x: (
            x.distance_km is None,
            x.distance_km if x.distance_km is not None else 1e9,
        )
    )
    return kept, stats


def default_suburb_label() -> str:
    df = load_suburbs()
    for candidate in (
        "Brisbane Adelaide Street, QLD 4000",
        "Brisbane City, QLD 4000",
        "South Brisbane, QLD 4101",
        "Sydney, NSW 2000",
        "Melbourne, VIC 3000",
    ):
        if (df["label"] == candidate).any():
            return candidate
    # Postcode 4000 (Brisbane CBD)
    pc = df[df["postcode"].astype(str).str.zfill(4) == "4000"]
    if not pc.empty:
        return str(pc.iloc[0]["label"])
    bris = df[
        df["suburb"].str.contains("Brisbane", case=False, na=False)
        & (df["state"].str.upper() == "QLD")
    ]
    if not bris.empty:
        return str(bris.iloc[0]["label"])
    return str(df.iloc[0]["label"]) if len(df) else "Brisbane"
