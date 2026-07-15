# Marketplace Deals Finder

Search **Facebook Marketplace**, **Gumtree AU**, **Carsales**, and **Locanto** at once. Results are merged and ranked by price + title match.

Default region: **Brisbane, Australia**.

## Features

- Multi-site search with deal scoring (parallel Facebook + Gumtree)
- **Dark / Light mode** toggle in the sidebar
- Card + table views, CSV export
- Min/max price, strict title match, hide free
- **All Australian suburbs** (state + search), with km radius
- Recent search history
- Result filters: site, title text, sort modes
- Fuzzy cross-site duplicate removal
- Streamlit web UI + CLI
- Desktop shortcut (`launch.bat`)

## Setup

```powershell
cd C:\Users\saltf\marketplace-deals
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## Run the app

```powershell
streamlit run app.py
```

Or double-click **Marketplace Deals Finder** on your Desktop.

### CLI

```powershell
python cli.py "gaming chair" --location Brisbane --max-price 150
python cli.py "iphone 13" --sources facebook,gumtree,locanto
```

## Sources

| Site | Notes |
|------|--------|
| Facebook Marketplace | Fast HTTP search |
| Gumtree AU | Safari-style fingerprint (avoids 403) |
| Carsales | Cars/vehicles; often WAF-blocked — see **Carsales workarounds** below |
| Locanto | Optional smaller classifieds site |

## Project layout

```
marketplace-deals/
  app.py
  cli.py
  launch.bat
  ui/theme.py              # dark/light CSS + card rendering
  scrapers/
    facebook.py
    gumtree.py
    locanto.py
    rank.py
    search.py
  .streamlit/config.toml
```

## Limitations

- No official listing APIs — public pages only
- Sites can change HTML or block bots
- Personal, low-volume use only

## Carsales workarounds

Carsales uses **AWS WAF + DataDome**. Many networks get hard **HTTP 403** on
`carsales.com.au`, so direct scraping fails.

The app tries, in order:

1. Direct HTTP (multiple browser fingerprints)
2. Optional warm browser session (`storage_state.json`)
3. **SERP discovery** (DuckDuckGo) for public `/cars/details/…` listing URLs

### Make Carsales work more reliably

| Method | How |
|--------|-----|
| **Residential proxy** | `set CARSALES_PROXY=http://user:pass@host:port` then search again |
| **Warm session** | `python warm_carsales_session.py` — solve CAPTCHA once, session is saved |
| **Force browser** | `set CARSALES_USE_BROWSER=1` then run a search (visible Chrome if needed) |
| **Open in browser** | Use the in-app **Carsales** link (always works manually) |

```powershell
# Example: proxy + search
$env:CARSALES_PROXY = "http://127.0.0.1:7890"
python cli.py "civic" --sources carsales --location "Brisbane Adelaide Street, QLD 4000" --max-price 25000
```

SERP fallback returns **real listing links + titles** (prices often N/A because
detail pages are also blocked). Radius filtering still applies when location
text can be geocoded.

## Troubleshooting

**Gumtree empty** — Retry, or open the Gumtree link from the UI expander.

**Facebook empty** — Retry; turn off “Facebook fast mode” if you need to log in.

**Carsales empty / 403** — See **Carsales workarounds** above.

**Theme** — Use **Appearance → Dark / Light** in the sidebar.
