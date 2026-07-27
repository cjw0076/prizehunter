#!/usr/bin/env bash
# browser_login.sh — open a HEADED Chromium with a persistent profile so you log in
# to Google/Kaggle ONCE (incl. 2FA); the session persists in .vault/chrome-profile
# and headless automation reuses it. RUN THIS ON A MACHINE WITH A DISPLAY.
# Nothing is exfiltrated; cookies stay in the local gitignored vault.
set -u
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
PROFILE="$PH_HOME/.vault/chrome-profile"; URL="${1:-https://www.kaggle.com/account/login}"
python3 - "$PROFILE" "$URL" <<'PY'
import sys
from playwright.sync_api import sync_playwright
profile, url = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(profile, headless=False,
            args=["--no-sandbox","--disable-dev-shm-usage"])
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto(url)
    print("Log in (Google/Gmail), complete 2FA, then close the window. Session saved to the vault.")
    try: pg.wait_for_event("close", timeout=600000)
    except Exception: pass
    ctx.close()
PY
