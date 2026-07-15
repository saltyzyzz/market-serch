"""Dark / light theme CSS for the deals finder."""

from __future__ import annotations

import html


def escape(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def theme_css(mode: str = "dark") -> str:
    dark = mode == "dark"

    # Palette
    if dark:
        bg = "#0b0d12"
        bg_elevated = "#141820"
        bg_card = "linear-gradient(160deg, #171b24 0%, #10141c 100%)"
        bg_sidebar = "#0f1218"
        border = "rgba(255,255,255,0.08)"
        border_strong = "rgba(255,255,255,0.14)"
        text = "#eef0f5"
        text_muted = "#9aa3b5"
        text_soft = "#6b7385"
        primary = "#3dd68c"
        primary_dim = "rgba(61, 214, 140, 0.14)"
        accent = "#6ea8fe"
        accent_fb = "#4c8dff"
        accent_gt = "#ff8f4c"
        accent_lc = "#c084fc"
        accent_cs = "#f43f5e"
        shadow = "0 10px 30px rgba(0,0,0,0.35)"
        input_bg = "#1a1f2a"
        hero_glow = "radial-gradient(ellipse 80% 60% at 20% 0%, rgba(61,214,140,0.18), transparent 55%), radial-gradient(ellipse 60% 50% at 90% 10%, rgba(110,168,254,0.12), transparent 50%)"
        metric_bg = "rgba(255,255,255,0.03)"
        table_header = "#1a1f2a"
    else:
        bg = "#f4f6fb"
        bg_elevated = "#ffffff"
        bg_card = "linear-gradient(160deg, #ffffff 0%, #f7f9fc 100%)"
        bg_sidebar = "#ffffff"
        border = "rgba(15, 23, 42, 0.08)"
        border_strong = "rgba(15, 23, 42, 0.12)"
        text = "#0f172a"
        text_muted = "#475569"
        text_soft = "#94a3b8"
        primary = "#059669"
        primary_dim = "rgba(5, 150, 105, 0.12)"
        accent = "#2563eb"
        accent_fb = "#1877f2"
        accent_gt = "#e85d04"
        accent_lc = "#7c3aed"
        accent_cs = "#e11d48"
        shadow = "0 10px 28px rgba(15, 23, 42, 0.08)"
        input_bg = "#ffffff"
        hero_glow = "radial-gradient(ellipse 80% 60% at 15% 0%, rgba(5,150,105,0.12), transparent 55%), radial-gradient(ellipse 60% 50% at 90% 10%, rgba(37,99,235,0.08), transparent 50%)"
        metric_bg = "rgba(15, 23, 42, 0.03)"
        table_header = "#f1f5f9"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: "DM Sans", system-ui, -apple-system, sans-serif;
    }}

    .stApp {{
        background: {bg};
        color: {text};
        background-image: {hero_glow};
        background-attachment: fixed;
    }}

    /* Main width / spacing */
    .block-container {{
        padding-top: 1.4rem !important;
        padding-bottom: 3rem !important;
        max-width: 1180px;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: {bg_sidebar} !important;
        border-right: 1px solid {border};
    }}
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 1.2rem;
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {{
        color: {text} !important;
    }}

    /* Headers */
    h1, h2, h3 {{
        font-family: "DM Sans", sans-serif !important;
        letter-spacing: -0.02em;
        color: {text} !important;
    }}

    /* Hero */
    .mdf-hero {{
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1.25rem;
        padding: 1.35rem 1.5rem;
        border-radius: 20px;
        border: 1px solid {border};
        background: {bg_card};
        box-shadow: {shadow};
    }}
    .mdf-hero-kicker {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: {primary};
        background: {primary_dim};
        border: 1px solid {border};
        border-radius: 999px;
        padding: 0.28rem 0.7rem;
        margin-bottom: 0.65rem;
    }}
    .mdf-hero h1 {{
        margin: 0 0 0.35rem 0 !important;
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        line-height: 1.15 !important;
    }}
    .mdf-hero p {{
        margin: 0;
        color: {text_muted};
        font-size: 1rem;
        max-width: 42rem;
        line-height: 1.5;
    }}
    .mdf-hero-pills {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.9rem;
    }}
    .mdf-pill {{
        font-size: 0.78rem;
        font-weight: 600;
        padding: 0.28rem 0.65rem;
        border-radius: 999px;
        border: 1px solid {border};
        background: {metric_bg};
        color: {text_muted};
    }}
    .mdf-pill.fb {{ color: {accent_fb}; border-color: color-mix(in srgb, {accent_fb} 35%, transparent); }}
    .mdf-pill.gt {{ color: {accent_gt}; border-color: color-mix(in srgb, {accent_gt} 35%, transparent); }}
    .mdf-pill.lc {{ color: {accent_lc}; border-color: color-mix(in srgb, {accent_lc} 35%, transparent); }}
    .mdf-pill.cs {{ color: {accent_cs}; border-color: color-mix(in srgb, {accent_cs} 35%, transparent); }}

    /* Metric cards */
    div[data-testid="stMetric"] {{
        background: {bg_card};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 0.85rem 1rem;
        box-shadow: {shadow};
    }}
    div[data-testid="stMetricLabel"] {{
        color: {text_muted} !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    div[data-testid="stMetricValue"] {{
        color: {text} !important;
        font-size: 1.55rem !important;
        font-weight: 700 !important;
        font-family: "JetBrains Mono", ui-monospace, monospace !important;
    }}

    /* Buttons */
    .stButton > button {{
        border-radius: 12px !important;
        font-weight: 600 !important;
        border: 1px solid {border_strong} !important;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }}
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, {primary}, color-mix(in srgb, {primary} 70%, {accent})) !important;
        color: {"#04140c" if dark else "#ffffff"} !important;
        border: none !important;
        box-shadow: 0 8px 20px {primary_dim} !important;
    }}
    .stButton > button:hover {{
        transform: translateY(-1px);
    }}

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div {{
        border-radius: 12px !important;
        background: {input_bg} !important;
        border-color: {border_strong} !important;
        color: {text} !important;
    }}

    /* Tabs */
    button[data-baseweb="tab"] {{
        font-weight: 600 !important;
        color: {text_muted} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {primary} !important;
    }}

    /* Source chips row */
    .mdf-source-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.4rem 0 1rem 0;
    }}
    .mdf-source-chip {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.4rem 0.75rem;
        border-radius: 999px;
        border: 1px solid {border};
        background: {metric_bg};
        font-size: 0.84rem;
        font-weight: 600;
        color: {text};
    }}
    .mdf-source-chip .n {{
        font-family: "JetBrains Mono", monospace;
        color: {primary};
        font-size: 0.8rem;
    }}
    .mdf-source-chip.zero .n {{ color: {text_soft}; }}

    /* Deal cards */
    .mdf-card-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 0.9rem;
    }}
    .mdf-card {{
        border: 1px solid {border};
        border-radius: 18px;
        padding: 1.05rem 1.15rem;
        background: {bg_card};
        box-shadow: {shadow};
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        min-height: 170px;
        transition: transform 0.12s ease, border-color 0.12s ease;
    }}
    .mdf-card:hover {{
        transform: translateY(-2px);
        border-color: {border_strong};
    }}
    .mdf-card-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }}
    .mdf-badge {{
        display: inline-flex;
        align-items: center;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }}
    .mdf-badge.fb {{ background: color-mix(in srgb, {accent_fb} 18%, transparent); color: {accent_fb}; }}
    .mdf-badge.gt {{ background: color-mix(in srgb, {accent_gt} 18%, transparent); color: {accent_gt}; }}
    .mdf-badge.lc {{ background: color-mix(in srgb, {accent_lc} 18%, transparent); color: {accent_lc}; }}
    .mdf-badge.cs {{ background: color-mix(in srgb, {accent_cs} 18%, transparent); color: {accent_cs}; }}
    .mdf-badge.other {{ background: {metric_bg}; color: {text_muted}; }}
    .mdf-rank {{
        font-size: 0.78rem;
        font-weight: 700;
        color: {text_soft};
        font-family: "JetBrains Mono", monospace;
    }}
    .mdf-title {{
        font-size: 1.02rem;
        font-weight: 650;
        line-height: 1.35;
        color: {text};
        flex: 1;
    }}
    .mdf-price {{
        font-family: "JetBrains Mono", monospace;
        font-weight: 700;
        font-size: 1.25rem;
        color: {primary};
        letter-spacing: -0.02em;
    }}
    .mdf-meta {{
        font-size: 0.86rem;
        color: {text_muted};
    }}
    .mdf-score {{
        font-size: 0.75rem;
        color: {text_soft};
        font-family: "JetBrains Mono", monospace;
    }}
    .mdf-link {{
        margin-top: auto;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.9rem;
        font-weight: 650;
        color: {accent} !important;
        text-decoration: none !important;
        padding-top: 0.35rem;
    }}
    .mdf-link:hover {{
        text-decoration: underline !important;
    }}

    /* Empty / welcome */
    .mdf-welcome {{
        border: 1px dashed {border_strong};
        border-radius: 20px;
        padding: 1.75rem 1.6rem;
        background: {bg_card};
        margin-top: 0.5rem;
    }}
    .mdf-welcome h3 {{
        margin-top: 0 !important;
        font-size: 1.2rem !important;
    }}
    .mdf-welcome ol {{
        color: {text_muted};
        line-height: 1.7;
        margin-bottom: 0;
    }}
    .mdf-steps {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
        margin-top: 1rem;
    }}
    .mdf-step {{
        border: 1px solid {border};
        border-radius: 14px;
        padding: 0.9rem 1rem;
        background: {metric_bg};
    }}
    .mdf-step .n {{
        font-family: "JetBrains Mono", monospace;
        color: {primary};
        font-weight: 700;
        font-size: 0.85rem;
    }}
    .mdf-step .t {{
        font-weight: 650;
        margin: 0.25rem 0;
        color: {text};
    }}
    .mdf-step .d {{
        font-size: 0.86rem;
        color: {text_muted};
        margin: 0;
    }}

    /* Dataframe polish */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {border};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: {shadow};
    }}

    /* Expander */
    div[data-testid="stExpander"] {{
        border: 1px solid {border};
        border-radius: 14px;
        background: {bg_elevated};
    }}

    /* Footer note */
    .mdf-footer {{
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid {border};
        color: {text_soft};
        font-size: 0.8rem;
        text-align: center;
    }}

    /* Creator credit — bottom-right corner */
    .mdf-credit {{
        position: fixed;
        right: 1rem;
        bottom: 0.75rem;
        z-index: 999;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.01em;
        color: {text_soft};
        background: color-mix(in srgb, {bg_elevated} 88%, transparent);
        border: 1px solid {border};
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        box-shadow: {shadow};
        pointer-events: none;
        user-select: none;
    }}
    .mdf-credit strong {{
        color: {text_muted};
        font-weight: 650;
    }}

    /* Alerts */
    div[data-testid="stAlert"] {{
        border-radius: 12px !important;
        border: 1px solid {border} !important;
    }}

    /* Download / secondary buttons */
    .stDownloadButton > button {{
        border-radius: 12px !important;
        font-weight: 600 !important;
    }}

    /* Link buttons */
    div[data-testid="stLinkButton"] a {{
        border-radius: 12px !important;
        font-weight: 600 !important;
        border: 1px solid {border_strong} !important;
        background: {metric_bg} !important;
        color: {text} !important;
    }}

    /* Captions */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {text_soft} !important;
    }}

    /* Slider / number polish */
    div[data-baseweb="slider"] {{
        padding-top: 0.25rem;
    }}

    /* Hide Streamlit chrome clutter a bit */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}

    /* Results heading spacing */
    .stMarkdown p strong {{
        color: {text};
    }}
    </style>
    """


def apply_theme(st_module, mode: str) -> None:
    st_module.markdown(theme_css(mode), unsafe_allow_html=True)


def site_badge_class(site: str) -> str:
    s = (site or "").lower()
    if "facebook" in s:
        return "fb"
    if "gumtree" in s:
        return "gt"
    if "locanto" in s:
        return "lc"
    if "carsales" in s or "car sales" in s:
        return "cs"
    return "other"


def render_deal_cards(st_module, rows: list[dict], *, columns: int = 3) -> None:
    """
    Render compact deal cards with native Streamlit widgets only.
    Avoids raw HTML so nothing shows as "lines of code".
    """
    if not rows:
        st_module.info("No listings match this filter.")
        return

    cols_n = max(1, min(columns, 3))
    for start in range(0, len(rows), cols_n):
        chunk = rows[start : start + cols_n]
        cols = st_module.columns(cols_n, gap="small")
        for col, row in zip(cols, chunk):
            with col:
                _render_one_card(st_module, row)


def score_color(score: float) -> str:
    """Deal score text color by band."""
    if score >= 80:
        return "#22c55e"  # green
    if score >= 65:
        return "#22d3ee"  # aqua
    if score >= 55:
        return "#eab308"  # yellow
    if score >= 40:
        return "#f97316"  # orange
    return "#ef4444"  # red


def _render_one_card(st_module, row: dict) -> None:
    site = str(row.get("site") or "Listing")
    title = str(row.get("title") or "Untitled")
    price = str(row.get("price_text") or "N/A")
    loc = str(row.get("location") or "")
    link = str(row.get("link") or "")
    image = row.get("image")
    dist = row.get("distance_km")
    dist_txt = ""
    try:
        if dist is not None and str(dist) not in {"", "nan", "None"}:
            dist_txt = f" · {float(dist):.0f} km away"
    except Exception:
        dist_txt = ""
    try:
        rank = int(row.get("rank") or 0)
    except Exception:
        rank = 0
    try:
        score_val = float(row.get("deal_score") or 0)
        score = f"{score_val:.0f}"
    except Exception:
        score_val = 0.0
        score = "—"

    color = score_color(score_val)
    # Shorten long titles for a tidy card
    short_title = title if len(title) <= 90 else title[:87].rstrip() + "…"

    with st_module.container(border=True):
        # Thumbnail
        if image and isinstance(image, str) and image.startswith("http"):
            try:
                st_module.image(image, use_container_width=True)
            except Exception:
                st_module.markdown(
                    '<div style="height:140px;border-radius:10px;background:rgba(127,127,127,0.15);'
                    'display:flex;align-items:center;justify-content:center;font-size:0.8rem;'
                    'opacity:0.7;margin-bottom:0.4rem;">No image</div>',
                    unsafe_allow_html=True,
                )
        else:
            st_module.markdown(
                '<div style="height:140px;border-radius:10px;background:rgba(127,127,127,0.15);'
                'display:flex;align-items:center;justify-content:center;font-size:0.8rem;'
                'opacity:0.7;margin-bottom:0.4rem;">No image</div>',
                unsafe_allow_html=True,
            )

        st_module.markdown(
            f'<p style="margin:0.35rem 0 0.35rem 0;font-size:0.82rem;opacity:0.9;">'
            f"#{rank} · {escape(site)} · score "
            f'<span style="color:{color};font-weight:700;">{escape(score)}</span>'
            f"</p>",
            unsafe_allow_html=True,
        )
        st_module.markdown(f"**{price}**")
        st_module.markdown(short_title)
        if loc or dist_txt:
            st_module.caption(f"{loc}{dist_txt}".strip(" ·"))
        if link and link.startswith("http"):
            st_module.link_button("Open listing", link, use_container_width=True)
