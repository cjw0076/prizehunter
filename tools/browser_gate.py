#!/usr/bin/env python3
"""browser_gate.py — handle a WEB gate directly with Browser Use, instead of
punting it to the operator.

Many "gates" are just a logged-in web action: accepting competition rules,
clicking Join, submitting a contact form, uploading a file. If the operator has a
logged-in browser profile, the agent can drive it — a web gate is NOT an operator
gate. This wraps a persistent-profile Playwright session so any tool/agent can:

  open   <url>                         open a page in the logged-in profile, snapshot it
  click  <url> "<button text>"         click a button by visible text (e.g. rules accept)
  accept <url>                         competition-rules pattern: Join → I Understand/Accept
  form   <url> field=val ... [--submit "<btn>"]   fill a contact form and optionally submit

The profile is the operator's real logged-in browser. Configure it once:
  export PH_BROWSER_PROFILE=/path/to/your/chrome-profile      # a dir with your sessions
(If unset, defaults to .vault/browser_profile under the repo — you log in there once.)

STILL operator-gated (never auto-fire): outbound cold email/DM to third parties,
spending money, creating new accounts. Everything else that's just a logged-in
click, do it here.

Requires: playwright (`pip install playwright && playwright install chromium`).
"""
import argparse
import os
import sys

PH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_PROFILE = os.path.join(PH, ".vault", "browser_profile")
PROFILE = os.environ.get("PH_BROWSER_PROFILE", DEFAULT_PROFILE)
ACCEPT_LABELS = ["I Understand and Accept", "Understand and Accept", "Accept",
                 "I Agree", "Agree", "Accept and Continue", "Join Competition"]


def _ctx(p, headless=True):
    os.makedirs(PROFILE, exist_ok=True)
    return p.chromium.launch_persistent_context(
        PROFILE, headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"])


def _page(ctx, url):
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)
    return pg


def cmd_open(a):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _ctx(p); pg = _page(ctx, a.url)
        body = pg.inner_text("body")[:1500]
        labels = [(b.inner_text() or "").strip() for b in pg.query_selector_all("button")]
        print("URL:", pg.url)
        print("TITLE:", pg.title())
        print("LOGGED_IN_GUESS:", "Sign In" not in body[:400] and "Register" not in body[:200])
        print("BUTTONS:", [l for l in labels if l][:25])
        print("BODY_HEAD:", body[:500].replace("\n", " | "))
        ctx.close()


def _click_first(pg, labels):
    for name in labels:
        try:
            pg.get_by_role("button", name=name, exact=False).first.click(timeout=4000)
            return name
        except Exception:
            continue
    return None


def cmd_click(a):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _ctx(p); pg = _page(ctx, a.url)
        got = _click_first(pg, [a.text])
        pg.wait_for_timeout(3000)
        print("CLICKED:", got or "NOT FOUND")
        ctx.close()


def cmd_accept(a):
    """Competition rules pattern: click Join, then the accept button in the modal."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _ctx(p); pg = _page(ctx, a.url)
        body0 = pg.inner_text("body")
        if "Sign In" in body0[:400]:
            print("NOT LOGGED IN — log into this profile once first (PH_BROWSER_PROFILE)."); ctx.close(); return
        _click_first(pg, ["Join Competition", "Join", "Enter Competition"])
        pg.wait_for_timeout(2500)
        # tick any consent checkbox, then accept
        for cb in pg.query_selector_all("input[type=checkbox]"):
            try:
                if not cb.is_checked():
                    cb.check(timeout=2000)
            except Exception:
                pass
        got = _click_first(pg, ACCEPT_LABELS)
        pg.wait_for_timeout(3000)
        still = "Join Competition" in pg.inner_text("body")
        print("ACCEPT_CLICKED:", got or "NONE", "| still_has_join:", still,
              "| ENTERED:", (got is not None and not still))
        ctx.close()


def cmd_form(a):
    from playwright.sync_api import sync_playwright
    fields = dict(kv.split("=", 1) for kv in a.pairs if "=" in kv)
    with sync_playwright() as p:
        ctx = _ctx(p); pg = _page(ctx, a.url)
        filled = []
        for name, val in fields.items():
            for sel in (f"[name='{name}']", f"#{name}", f"textarea[name='{name}']",
                        f"input[placeholder*='{name}' i]", f"textarea[placeholder*='{name}' i]"):
                el = pg.query_selector(sel)
                if el:
                    try:
                        el.fill(val, timeout=3000); filled.append(name); break
                    except Exception:
                        continue
        print("FILLED:", filled, "| MISSED:", [f for f in fields if f not in filled])
        if a.submit:
            got = _click_first(pg, [a.submit])
            pg.wait_for_timeout(3000)
            print("SUBMIT:", got or "NOT FOUND")
        else:
            print("(dry-run: not submitted — pass --submit \"<button>\" to send)")
        ctx.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    o = sub.add_parser("open"); o.add_argument("url")
    c = sub.add_parser("click"); c.add_argument("url"); c.add_argument("text")
    ac = sub.add_parser("accept"); ac.add_argument("url")
    f = sub.add_parser("form"); f.add_argument("url"); f.add_argument("pairs", nargs="*")
    f.add_argument("--submit", default="")
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help(); sys.exit(0)
    try:
        {"open": cmd_open, "click": cmd_click, "accept": cmd_accept, "form": cmd_form}[a.cmd](a)
    except ModuleNotFoundError:
        print("playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)


if __name__ == "__main__":
    main()
