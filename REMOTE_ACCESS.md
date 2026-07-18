# Marketplace Deals Finder — copy on `D:\WEB APP`

Full copy of the solid app, with remote access helpers.

## First-time setup (this PC)

1. Double-click **`setup.bat`**
2. Wait until pip + Playwright finish
3. Then use one of the launchers below

## How to open the app

| Goal | What to run | URL |
|------|-------------|-----|
| Use on this PC only | `launch.bat` | http://localhost:8501 |
| Phone / other PC on same Wi‑Fi | `launch_remote.bat` | http://**YOUR_LAN_IP**:8501 |
| From the internet (anywhere) | `launch_tunnel.bat` | https://….trycloudflare.com |

### LAN (same Wi‑Fi) steps

1. (Once, as Admin) run **`allow_firewall.bat`**
2. Run **`launch_remote.bat`**
3. Note the IP it prints, e.g. `http://192.168.1.42:8501`
4. On your phone/tablet (same Wi‑Fi), open that URL in the browser

### Internet (outside home)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)  
   or: `winget install --id Cloudflare.cloudflared`
2. Run **`launch_tunnel.bat`**
3. Copy the `https://….trycloudflare.com` link it shows  
   Anyone with the link can use the app while your PC is on and the tunnel is running.

> Temporary tunnels are not password-protected. Don’t share the link publicly.

## Files in this folder

- `app.py` — Streamlit UI  
- `scrapers/` — Facebook Marketplace + Gumtree only  

- `data/au_suburbs.csv` — suburb list  
- `setup.bat` / `launch.bat` / `launch_remote.bat` / `launch_tunnel.bat` / `allow_firewall.bat`

## Stop the app

Close the **Marketplace Deals Finder** console window, or end the Streamlit process in Task Manager.
