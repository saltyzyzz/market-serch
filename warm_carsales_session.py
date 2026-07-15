"""
Warm a Carsales browser session (solve CAPTCHA once).

Usage:
  .\\.venv\\Scripts\\python.exe warm_carsales_session.py

A Chromium window opens on carsales.com.au. If you see a CAPTCHA/challenge,
complete it, browse to a search page until listings appear, then return here
and press Enter. Cookies are saved for future automated runs.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".browser-data-carsales"
STORAGE = DATA / "storage_state.json"


async def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    print("Opening Carsales in Chrome…")
    print("1) Pass any CAPTCHA if shown")
    print("2) Run a search until you see car listings")
    print("3) Come back here and press Enter to save the session\n")

    async with async_playwright() as p:
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(DATA / "profile"),
                channel="chrome",
                headless=False,
                locale="en-AU",
                viewport={"width": 1400, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(locale="en-AU")
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.carsales.com.au/", wait_until="domcontentloaded")
        await page.goto(
            "https://www.carsales.com.au/cars/?q=(And.Keyword.civic._.State.Queensland.)",
            wait_until="domcontentloaded",
        )

        await asyncio.get_event_loop().run_in_executor(
            None, lambda: input("Press Enter after listings are visible… ")
        )

        state = await context.storage_state()
        STORAGE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"Saved session → {STORAGE}")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
