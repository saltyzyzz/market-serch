from __future__ import annotations

from pathlib import Path

from playwright.async_api import BrowserContext, Playwright, async_playwright

# Persist cookies so Facebook login can survive across runs
BROWSER_DATA = Path(__file__).resolve().parent.parent / ".browser-data"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


async def open_context(
    playwright: Playwright,
    *,
    headless: bool = True,
    persistent: bool = True,
    channel: str | None = None,
) -> BrowserContext:
    """Launch a Chromium context, optionally with saved session data."""
    BROWSER_DATA.mkdir(parents=True, exist_ok=True)
    extra = {"channel": channel} if channel else {}

    if persistent:
        try:
            return await playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_DATA),
                headless=headless,
                viewport={"width": 1400, "height": 900},
                user_agent=USER_AGENT,
                locale="en-AU",
                args=["--disable-blink-features=AutomationControlled"],
                **extra,
            )
        except Exception:
            if channel:
                return await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(BROWSER_DATA),
                    headless=headless,
                    viewport={"width": 1400, "height": 900},
                    user_agent=USER_AGENT,
                    locale="en-AU",
                    args=["--disable-blink-features=AutomationControlled"],
                )
            raise

    try:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            **extra,
        )
    except Exception:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
    return await browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent=USER_AGENT,
        locale="en-AU",
    )


async def new_page(context: BrowserContext):
    page = await context.new_page()
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return page


# Re-export for convenience
async_playwright = async_playwright
