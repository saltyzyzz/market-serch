"""
Marketplace Deals Finder — Facebook Marketplace + Gumtree
Run:  streamlit run app.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.facebook import build_facebook_url
from scrapers.gumtree import build_gumtree_url
from scrapers.locations import (
    STATES,
    default_suburb_label,
    filter_suburb_labels,
    load_suburbs,
    resolve_location,
)
from scrapers.search import search_all
from ui.theme import apply_theme, escape, render_deal_cards

st.set_page_config(
    page_title="Marketplace Deals Finder",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

SOURCE_OPTIONS = {
    "Facebook Marketplace": "facebook",
    "Gumtree": "gumtree",
}
DEFAULT_SOURCES = ["Facebook Marketplace", "Gumtree"]
MAX_RECENT = 8


def max_value_ok(v) -> bool:
    try:
        return float(v) > 0
    except Exception:
        return False


def push_recent(query: str, location: str) -> None:
    item = {"q": query, "loc": location}
    recent = st.session_state.get("recent_searches") or []
    recent = [r for r in recent if not (r.get("q") == query and r.get("loc") == location)]
    recent.insert(0, item)
    st.session_state["recent_searches"] = recent[:MAX_RECENT]


def run_marketplace_search(
    *,
    query: str,
    location: str,
    max_price: float | None,
    min_price: float | None,
    limit: int,
    source_keys: list[str],
    headless_fb: bool,
    hide_free: bool,
    strict_match: bool,
    radius_km: int = 50,
) -> None:
    with st.spinner("Searching Facebook, Gumtree… usually a few seconds"):
        try:
            _listings, df = asyncio.run(
                search_all(
                    query=query,
                    location=location,
                    max_price=max_price,
                    min_price=min_price,
                    limit=limit,
                    sources=source_keys,
                    headless_fb=headless_fb,
                    headless_gt=True,
                    parallel=True,
                    hide_free=hide_free,
                    min_relevance=0.34 if strict_match else 0.0,
                    radius_km=radius_km,
                )
            )
            st.session_state["last_df"] = df
            st.session_state["last_query"] = query
            st.session_state["last_location"] = location
            st.session_state["last_radius_km"] = int(radius_km)
            st.session_state["errors"] = df.attrs.get("errors", [])
            st.session_state["source_counts"] = df.attrs.get("source_counts", {})
            st.session_state["source_timings"] = df.attrs.get("source_timings", {})
            st.session_state["elapsed_sec"] = df.attrs.get("elapsed_sec")
            st.session_state["radius_stats"] = df.attrs.get("radius_stats", {})
            st.session_state["search_centre"] = df.attrs.get("search_centre", {})
            st.session_state["sweep_report"] = df.attrs.get("sweep_report", {})
            st.session_state["last_sources"] = source_keys
            push_recent(query, location)
        except Exception as e:
            st.error(f"Search failed: {e}")
            st.session_state.pop("last_df", None)


# ---- sidebar ----
with st.sidebar:
    st.markdown("### 🛒 Deals Finder")
    st.caption("Compare local marketplaces in one place.")

    theme_choice = st.radio(
        "Appearance",
        options=["Dark", "Light"],
        horizontal=True,
        key="theme_choice",
        help="Switch between dark and light mode",
    )
    theme_mode = "dark" if theme_choice == "Dark" else "light"

    st.divider()

    with st.form("search_form", clear_on_submit=False):
        st.markdown("#### Search")
        query = st.text_input(
            "What are you looking for?",
            placeholder="gaming chair, iPhone 13, lawn mower…",
            key="query_input",
        )

        st.markdown("#### Location")
        loc_state = st.selectbox(
            "State / territory",
            options=STATES,
            index=0,
            help="Filter the suburb list by state",
        )
        suburb_search = st.text_input(
            "Find suburb",
            placeholder="Type suburb name or postcode…",
            help=f"Search {len(load_suburbs()):,} Australian suburbs",
        )
        # Full state lists are fine; "All" without search stays capped for UI speed
        suburb_limit = 5000 if loc_state != "All" or suburb_search.strip() else 800
        suburb_opts = filter_suburb_labels(
            state=loc_state,
            search=suburb_search,
            limit=suburb_limit,
        )
        if not suburb_opts:
            st.caption("No suburbs match — try another spelling or state.")
            suburb_opts = [default_suburb_label()]

        default_label = default_suburb_label()
        default_idx = (
            suburb_opts.index(default_label) if default_label in suburb_opts else 0
        )
        location = st.selectbox(
            "Suburb",
            options=suburb_opts,
            index=default_idx,
            help="Every Australian suburb/locality is available — filter with state + search",
        )
        resolved_preview = resolve_location(location)
        st.caption(
            f"Using **{resolved_preview.suburb}** · "
            f"{resolved_preview.lat:.3f}, {resolved_preview.lng:.3f} · "
            f"hub {resolved_preview.gumtree_region.title()}"
        )

        radius_km = st.select_slider(
            "Radius (km)",
            options=[5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300, 500],
            value=50,
            help="How far from the selected suburb to include listings",
        )

        c_min, c_max = st.columns(2)
        with c_min:
            min_price = st.number_input(
                "Min $",
                min_value=0,
                value=0,
                step=25,
                help="0 = no minimum",
            )
        with c_max:
            max_price = st.number_input(
                "Max $",
                min_value=0,
                value=0,
                step=50,
                help="0 = no maximum",
            )

        limit = st.slider("Results per site", min_value=5, max_value=40, value=20, step=5)

        sources = st.multiselect(
            "Sources",
            options=list(SOURCE_OPTIONS.keys()),
            default=DEFAULT_SOURCES,
        )

        c_free, c_strict = st.columns(2)
        with c_free:
            hide_free = st.checkbox("Hide free", value=False)
        with c_strict:
            strict_match = st.checkbox(
                "Strict match",
                value=True,
                help="Only show listings whose titles match your search terms",
            )

        with st.expander("Advanced", expanded=False):
            st.checkbox(
                "Facebook fast mode",
                value=True,
                key="headless_fb",
                help="Uses HTTP first. Turn off only if you need a login window.",
            )
            st.caption(
                "Personal research only. Be gentle with search volume and respect each site's terms."
            )

        search_btn = st.form_submit_button(
            "Search deals",
            type="primary",
            use_container_width=True,
        )

    headless_fb = bool(st.session_state.get("headless_fb", True))

    recent = st.session_state.get("recent_searches") or []
    if recent:
        st.caption("Recent")
        for i, r in enumerate(recent[:5]):
            label = f"{r.get('q', '')} · {r.get('loc', '')}"
            if st.button(label, key=f"recent_{i}", use_container_width=True):
                st.session_state["query_input"] = r.get("q", "")
                st.session_state["pending_recent"] = r

    if st.session_state.get("last_df") is not None:
        if st.button("Clear results", use_container_width=True):
            for k in (
                "last_df",
                "last_query",
                "last_location",
                "last_radius_km",
                "errors",
                "source_counts",
                "source_timings",
                "elapsed_sec",
                "radius_stats",
                "search_centre",
                "sweep_report",
                "last_sources",
            ):
                st.session_state.pop(k, None)
            st.rerun()

apply_theme(st, theme_mode)

source_keys = [SOURCE_OPTIONS[s] for s in sources if s in SOURCE_OPTIONS]

# ---- hero ----
st.markdown(
    """
    <div class="mdf-hero">
      <div>
        <div class="mdf-hero-kicker">🇦🇺 Australia · local deals</div>
        <h1>Marketplace Deals Finder</h1>
        <p>Search Facebook Marketplace and Gumtree together — then rank the best prices near you.</p>
        <div class="mdf-hero-pills">
          <span class="mdf-pill fb">Facebook Marketplace</span>
          <span class="mdf-pill gt">Gumtree</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _price_or_none(v) -> float | None:
    return float(v) if max_value_ok(v) else None


# Handle recent-search triggers
pending_recent = st.session_state.pop("pending_recent", None)

if pending_recent and isinstance(pending_recent, dict):
    run_marketplace_search(
        query=str(pending_recent.get("q") or "").strip(),
        location=str(pending_recent.get("loc") or location),
        max_price=_price_or_none(max_price),
        min_price=_price_or_none(min_price),
        limit=int(limit),
        source_keys=source_keys or ["facebook", "gumtree"],
        headless_fb=headless_fb,
        hide_free=hide_free,
        strict_match=strict_match,
        radius_km=int(radius_km),
    )
elif search_btn:
    if not query.strip():
        st.warning("Enter something to search for.")
    elif not source_keys:
        st.warning("Pick at least one source.")
    else:
        run_marketplace_search(
            query=query.strip(),
            location=location,
            max_price=_price_or_none(max_price),
            min_price=_price_or_none(min_price),
            limit=int(limit),
            source_keys=source_keys,
            headless_fb=headless_fb,
            hide_free=hide_free,
            strict_match=strict_match,
            radius_km=int(radius_km),
        )

df: pd.DataFrame | None = st.session_state.get("last_df")
active_sources = st.session_state.get("last_sources") or source_keys
q_display = st.session_state.get("last_query") or (query.strip() if query else "")
loc_display = st.session_state.get("last_location") or location
radius_display = st.session_state.get("last_radius_km") or int(radius_km)

if df is not None:
    errors = st.session_state.get("errors") or []
    counts = st.session_state.get("source_counts") or {}
    timings = st.session_state.get("source_timings") or {}
    elapsed = st.session_state.get("elapsed_sec")

    header_bits = []
    if q_display:
        header_bits.append(
            f"**Results for** `{escape(q_display)}` **near** `{escape(loc_display)}` "
            f"**within {int(radius_display)} km**"
        )
    if elapsed is not None:
        header_bits.append(f"· searched in **{elapsed}s**")
    if header_bits:
        st.markdown(" ".join(header_bits))

    if counts:
        chips = []
        for name, n in counts.items():
            zero = " zero" if not n else ""
            t = timings.get(name)
            t_bit = f" · {t}s" if t is not None else ""
            chips.append(
                f'<span class="mdf-source-chip{zero}">{escape(name)} '
                f'<span class="n">{int(n)}</span>{escape(t_bit)}</span>'
            )
        st.markdown(
            f'<div class="mdf-source-row">{"".join(chips)}</div>',
            unsafe_allow_html=True,
        )

    rstats = st.session_state.get("radius_stats") or {}
    if rstats:
        st.caption(
            f"Radius filter: **{rstats.get('within', 0)}** within {int(radius_display)} km · "
            f"**{rstats.get('outside', 0)}** too far removed · "
            f"**{rstats.get('unknown', 0)}** location unknown"
            + (" (unknowns kept)" if rstats.get("kept_unknown") else "")
        )

    sweeps = st.session_state.get("sweep_report") or {}
    if sweeps:
        bits = []
        for site, rows in sweeps.items():
            if not rows:
                continue
            parts = []
            for row in rows:
                name = row.get("sweep") or "?"
                if row.get("skipped"):
                    parts.append(f"{name}=skip")
                elif row.get("error"):
                    parts.append(f"{name}=err")
                else:
                    n = row.get("new_unique", row.get("new", row.get("count", 0)))
                    parts.append(f"{name}+{n}")
            bits.append(f"**{site}**: {', '.join(parts)}")
        if bits:
            st.caption("3-sweep scan · " + " · ".join(bits))

    for err in errors:
        st.warning(f"⚠️ {err}")

    mp = _price_or_none(max_price)
    rk = int(radius_display)
    with st.expander(
        "Open the same search in your browser",
        expanded=bool(errors) and df.empty,
    ):
        cols = st.columns(2)
        if "facebook" in active_sources and q_display:
            cols[0].link_button(
                "Facebook Marketplace",
                build_facebook_url(q_display, loc_display, mp, radius_km=rk),
                use_container_width=True,
            )
        if "gumtree" in active_sources and q_display:
            cols[1].link_button(
                "Gumtree",
                build_gumtree_url(q_display, loc_display, mp, radius_km=rk),
                use_container_width=True,
            )

    if df.empty:
        st.info(
            "No listings found. Try turning off **Strict match**, broaden the query, "
            "raise max price, or open the marketplace links above."
        )
    else:
        priced = df["price"].dropna()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Listings", f"{len(df)}")
        m2.metric("Cheapest", f"${priced.min():,.0f}" if len(priced) else "—")
        m3.metric("Median", f"${priced.median():,.0f}" if len(priced) else "—")
        m4.metric("Sites hit", f"{df['site'].nunique()}")

        f1, f2, f3 = st.columns([2, 1, 1])
        with f1:
            site_filter = st.multiselect(
                "Filter by site",
                options=sorted(df["site"].dropna().unique().tolist()),
                default=sorted(df["site"].dropna().unique().tolist()),
                key="result_site_filter",
            )
        with f2:
            sort_by = st.selectbox(
                "Sort by",
                options=[
                    "Best deal score",
                    "Closest first",
                    "Lowest price",
                    "Highest price",
                    "Best title match",
                    "Site A–Z",
                ],
                key="result_sort",
            )
        with f3:
            text_filter = st.text_input(
                "Title contains",
                placeholder="filter…",
                key="result_text_filter",
            )

        view = df.copy()
        if site_filter:
            view = view[view["site"].isin(site_filter)]
        if text_filter.strip():
            needle = text_filter.strip().lower()
            view = view[view["title"].astype(str).str.lower().str.contains(needle, na=False)]

        if sort_by == "Closest first" and "distance_km" in view.columns:
            view = view.sort_values(
                by=["distance_km", "deal_score"],
                ascending=[True, False],
                na_position="last",
            )
        elif sort_by == "Lowest price":
            view = view.sort_values(
                by=["price", "deal_score"], ascending=[True, False], na_position="last"
            )
        elif sort_by == "Highest price":
            view = view.sort_values(
                by=["price", "deal_score"], ascending=[False, False], na_position="last"
            )
        elif sort_by == "Best title match":
            col = "relevance" if "relevance" in view.columns else "deal_score"
            view = view.sort_values(by=[col, "price"], ascending=[False, True], na_position="last")
        elif sort_by == "Site A–Z":
            view = view.sort_values(by=["site", "deal_score"], ascending=[True, False])
        else:
            view = view.sort_values(
                by=["deal_score", "price"], ascending=[False, True], na_position="last"
            )
        view = view.reset_index(drop=True)
        view["rank"] = range(1, len(view) + 1)

        st.caption(f"Showing **{len(view)}** of **{len(df)}** listings")

        tab_cards, tab_table = st.tabs(["Cards", "Table"])

        with tab_cards:
            if view.empty:
                st.info("No listings match this filter.")
            else:
                # Native Streamlit cards only — no raw HTML dump
                render_deal_cards(
                    st,
                    [row.to_dict() for _, row in view.head(48).iterrows()],
                    columns=3,
                )

        with tab_table:
            if view.empty:
                st.info("No listings match this filter.")
            else:
                cols = [
                    "rank",
                    "site",
                    "title",
                    "price_text",
                    "location",
                    "distance_km",
                    "link",
                    "deal_score",
                ]
                if "relevance" in view.columns:
                    cols.insert(-1, "relevance")
                show = view[[c for c in cols if c in view.columns]].copy()
                if "relevance" in show.columns:
                    show["relevance"] = (show["relevance"].astype(float) * 100).round(0)
                rename = {
                    "rank": "#",
                    "site": "Site",
                    "title": "Title",
                    "price_text": "Price",
                    "location": "Location",
                    "distance_km": "Km",
                    "link": "Link",
                    "deal_score": "Score",
                    "relevance": "Match %",
                }
                show = show.rename(columns=rename)
                st.dataframe(
                    show,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                        "Score": st.column_config.ProgressColumn(
                            "Deal score",
                            min_value=0,
                            max_value=100,
                            format="%.0f",
                        ),
                        "Match %": st.column_config.ProgressColumn(
                            "Title match",
                            min_value=0,
                            max_value=100,
                            format="%.0f%%",
                        ),
                    },
                )
                st.download_button(
                    "Download CSV",
                    data=view.to_csv(index=False),
                    file_name=f"deals_{(q_display or 'search').replace(' ', '_')}.csv",
                    mime="text/csv",
                )
else:
    st.markdown(
        """
        <div class="mdf-welcome">
          <h3>How it works</h3>
          <div class="mdf-steps">
            <div class="mdf-step">
              <div class="n">01</div>
              <div class="t">Describe the item</div>
              <p class="d">Type what you want in the sidebar — chairs, phones, tools…</p>
            </div>
            <div class="mdf-step">
              <div class="n">02</div>
              <div class="t">Set suburb & radius</div>
              <p class="d">Any Australian suburb, km radius, budget filters, and sources.</p>
            </div>
            <div class="mdf-step">
              <div class="n">03</div>
              <div class="t">Get ranked deals</div>
              <p class="d">Results are scored by price + title match, with duplicates removed.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="mdf-footer">Personal deal-hunting tool · not affiliated with Facebook or Gumtree</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="mdf-credit">© <strong>JJD</strong> 2026</div>',
    unsafe_allow_html=True,
)
