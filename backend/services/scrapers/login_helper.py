"""One-off helper to log into each auction site and save a Playwright
storage_state file. Run interactively — a visible browser window opens,
you log in by hand, and when you press Enter in the terminal the cookies
are saved.

Usage:
    python -m backend.services.scrapers.login_helper copart
    python -m backend.services.scrapers.login_helper iaai
    python -m backend.services.scrapers.login_helper amerpol
"""
from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

from backend.services.scrapers.base import storage_state_path

URLS = {
    "copart": "https://www.copart.com/login/",
    "iaai": "https://login.iaai.com/",
    "amerpol": "https://amerpol.pl/logowanie",
}


async def main(site: str) -> None:
    if site not in URLS:
        print(f"Unknown site {site!r}. Options: {list(URLS)}")
        sys.exit(1)
    out = storage_state_path(site)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(URLS[site])
        print(f"\nZaloguj się ręcznie w oknie przeglądarki na {site}.")
        input("Gdy jesteś już zalogowany, naciśnij Enter tutaj — zapiszę sesję... ")
        await context.storage_state(path=str(out))
        print(f"Zapisano: {out}")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.services.scrapers.login_helper <copart|iaai|amerpol>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
