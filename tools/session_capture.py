#!/usr/bin/env python3
"""session_capture.py — turn a one-time web login into an API token, automatically.

The web-login gate (DACON, Kaggle, portals) is the main thing that stops unattended
operation. This tool collapses it: the operator logs in ONCE (or supplies creds),
then the agent drives the browser's dev-tools/network layer to extract the auth
token (JWT / Bearer header / session cookie), stores it in the vault, and verifies
it against the API. Every subsequent call is then agent-only.

Requires playwright:  pip install playwright && python -m playwright install chromium

usage:
  session_capture.py --site dacon --headed        # you log in in the opened window
  session_capture.py --site dacon --creds          # auto-login from vault (SITE_EMAIL/SITE_PW)
  session_capture.py --site dacon --storage state.json   # reuse an existing logged-in session
  session_capture.py --list                        # show known site profiles

What it captures (in order): a Bearer token seen on any XHR Authorization header,
then any JWT (eyJ…) found in localStorage or cookies. Stores it as the site's
vault key. Nothing secret is printed.
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}")

# Per-site profiles. Selectors are best-effort; --headed always works (human logs in).
SITES = {
    "dacon": {
        "home": "https://dacon.io/",
        "login": "https://dacon.io/",
        "ready_host": "dacon.io",
        "api_ping": "https://app.dacon.io/api/v1/subscription/user-status",
        "trigger_paths": ["https://dacon.io/myPage/", "https://dacon.io/"],
        "vault_key": "DACON_JWT",
        "email_sel": "input[type=email], input[name=email], #email",
        "pw_sel": "input[type=password], #password",
        "submit_sel": "button[type=submit], button:has-text('로그인')",
    },
    "kaggle": {
        "home": "https://www.kaggle.com/",
        "login": "https://www.kaggle.com/account/login",
        "ready_host": "kaggle.com",
        "api_ping": "https://www.kaggle.com/api/i/users.UsersService/GetCurrentUser",
        "trigger_paths": ["https://www.kaggle.com/competitions"],
        "vault_key": "KAGGLE_SESSION_JWT",
        "email_sel": "input[name=email]",
        "pw_sel": "input[name=password]",
        "submit_sel": "button[type=submit]",
    },
}


def store(key, value):
    subprocess.run(["bash", os.path.join(HERE, "vault_set.sh"), key, value],
                   input=value, text=True, check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site")
    ap.add_argument("--headed", action="store_true", help="open a window and let the human log in")
    ap.add_argument("--creds", action="store_true", help="auto-login from vault <SITE>_EMAIL/<SITE>_PW")
    ap.add_argument("--storage", help="reuse an existing playwright storage_state json")
    ap.add_argument("--wait", type=int, default=180, help="seconds to wait for login (headed)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.site:
        print("known site profiles:", ", ".join(SITES))
        print("add your own by extending SITES in this file.")
        return
    prof = SITES.get(a.site)
    if not prof:
        sys.exit(f"unknown site '{a.site}'. Known: {', '.join(SITES)} (or add a profile).")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright missing → pip install playwright && python -m playwright install chromium")

    captured = {"bearer": None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not a.headed, args=["--no-sandbox"])
        ctx = browser.new_context(storage_state=a.storage) if a.storage else browser.new_context()
        pg = ctx.new_page()

        def on_req(req):
            if captured["bearer"]:
                return
            auth = req.headers.get("authorization") or req.headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                tok = auth.split(None, 1)[1]
                if JWT.search(tok) or len(tok) > 20:
                    captured["bearer"] = tok
        pg.on("request", on_req)

        pg.goto(prof["login"], timeout=60000)
        pg.wait_for_timeout(2500)

        if a.creds and not a.storage:
            pre = a.site.upper()
            email = os.environ.get(f"{pre}_EMAIL", "")
            pw = os.environ.get(f"{pre}_PW", "")
            if email and pw:
                for sel, val in ((prof["email_sel"], email), (prof["pw_sel"], pw)):
                    try:
                        pg.fill(sel, val, timeout=8000)
                    except Exception:
                        pass
                try:
                    pg.click(prof["submit_sel"], timeout=8000)
                except Exception:
                    pass
                pg.wait_for_timeout(5000)
            else:
                print(f"--creds needs {pre}_EMAIL and {pre}_PW in the environment/vault; falling through.")

        if a.headed and not a.storage:
            print(f"→ log in to {a.site} in the opened window. Waiting up to {a.wait}s…")
            deadline = time.time() + a.wait
            while time.time() < deadline and prof["ready_host"] not in pg.url:
                pg.wait_for_timeout(2000)

        # trigger API traffic so an Authorization header appears, then scrape storage
        for u in prof.get("trigger_paths", []):
            try:
                pg.goto(u, timeout=30000); pg.wait_for_timeout(2500)
            except Exception:
                pass
            if captured["bearer"]:
                break

        token = captured["bearer"]
        source = "network Authorization header"
        if not token:
            # localStorage
            try:
                ls = pg.evaluate("() => JSON.stringify(window.localStorage)")
                m = JWT.search(ls or "")
                if m:
                    token = m.group(0); source = "localStorage"
            except Exception:
                pass
        if not token:
            for c in ctx.cookies():
                if JWT.search(c.get("value", "")):
                    token = c["value"]; source = f"cookie {c.get('name')}"; break

        # save storage_state for reuse regardless
        try:
            ctx.storage_state(path=os.path.join(HERE, f".session_{a.site}.json"))
        except Exception:
            pass
        browser.close()

    if token:
        store(prof["vault_key"], token)
        print(f"captured {a.site} token from {source} → vault {prof['vault_key']} "
              f"(len {len(token)}, value hidden). API access is now agent-driven.")
        print(f"verify: curl -s -H 'Authorization: Bearer <{prof['vault_key']}>' {prof['api_ping']}")
    else:
        print(f"no token captured for {a.site}. Try --headed and log in fully, then re-run; "
              f"or the site may keep auth in an httpOnly cookie (reuse --storage .session_{a.site}.json).")
        sys.exit(1)


if __name__ == "__main__":
    main()
