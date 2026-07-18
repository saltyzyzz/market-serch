# Marketplace Deals Finder

Search **Facebook Marketplace** and **Gumtree AU** at once. Results are merged and ranked by price + title match.

## Run (this folder)

```bat
setup.bat
launch.bat
```

- Local: `launch.bat` → http://localhost:8501  
- Same Wi‑Fi: `launch_remote.bat`  
- Internet tunnel: `launch_tunnel.bat` (needs cloudflared)

## CLI

```bat
.venv\Scripts\python.exe cli.py "gaming chair" --location "Brisbane" --max-price 300
```

Sources are only `facebook` and `gumtree`.

## Notes

- Personal research tool — respect each site’s terms.  
- Some networks block marketplace sites; use **Open Facebook / Gumtree** links if scrapers return empty.
