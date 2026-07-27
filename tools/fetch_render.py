#!/usr/bin/env python3
"""fetch_render.py — headless-Chrome fetch for JS-rendered competition listings.

Many platforms (Kaggle, Devpost, culture.go.kr, qhackathon, ...) render their
lists client-side, so curl gets an empty shell. This uses Playwright/Chromium to
load the page, wait for content, and print the rendered HTML to stdout — the same
fetch primitive discover_contests.py uses for `render=browser` sources.

Usage: fetch_render.py <url> [--wait-selector SEL] [--timeout MS] [--scroll N]
"""
import sys, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--wait-selector", default=None)
    ap.add_argument("--timeout", type=int, default=30000)
    ap.add_argument("--scroll", type=int, default=0, help="scroll N times to load lazy lists")
    ap.add_argument("--profile", default=None, help="persistent profile dir (authenticated session)")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"playwright unavailable: {e}", file=sys.stderr); sys.exit(9)

    with sync_playwright() as p:
        if a.profile:
            b = p.chromium.launch_persistent_context(a.profile, headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
            pg = b.pages[0] if b.pages else b.new_page()
        else:
            b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            pg = b.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) PrizeHunter/1.0")
        try:
            pg.goto(a.url, timeout=a.timeout, wait_until="domcontentloaded")
            if a.wait_selector:
                try: pg.wait_for_selector(a.wait_selector, timeout=a.timeout)
                except Exception: pass
            else:
                pg.wait_for_timeout(2500)
            for _ in range(a.scroll):
                pg.mouse.wheel(0, 12000); pg.wait_for_timeout(1200)
            html = pg.content()
        finally:
            b.close()
    sys.stdout.write(html)

if __name__ == "__main__":
    main()
