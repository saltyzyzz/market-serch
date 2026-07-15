from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Listing:
    site: str
    title: str
    price: float | None
    price_text: str
    link: str
    location: str
    image: str | None = None
    distance_km: float | None = None
    lat: float | None = None
    lng: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Gumtree Australia location IDs (region-level)
GUMTREE_LOCATIONS: dict[str, str] = {
    "australia": "3008849",
    "brisbane": "3005721",
    "sydney": "3003435",
    "melbourne": "3005249",
    "perth": "3008305",
    "adelaide": "3003991",
    "gold coast": "3006177",
    "canberra": "3004601",
    "hobart": "3004389",
    "darwin": "3004005",
    "newcastle": "3003439",
}

# Facebook Marketplace lat/long for major AU cities
FB_COORDS: dict[str, tuple[float, float]] = {
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
