#!/usr/bin/env python3
"""Devpost submission automation — runs AFTER a Devpost account exists.

Devpost LOGIN has no CAPTCHA (only signup does), so once the founder creates the
account (the one human bot-check), this script can drive the rest: log in, join
each hackathon, create a submission draft, and fill every field from
devpost_submissions.json + each project's about_file. It STOPS before the final
"Submit" (leaves a draft) and screenshots each step for founder review.

Usage:
  # creds via env (never written to disk by this script):
  DEVPOST_EMAIL=cjw070690@gmail.com DEVPOST_PW="$(cat control_tower/.secrets/devpost_pw.txt)" \
    python3 control_tower/tools/devpost_submit.py [--only rapid,splunk] [--login-check]

  --login-check : just verify login works and screenshot the dashboard, do nothing else.
  --only KEYS   : restrict to comma-separated submission keys.

Notes:
- Devpost submission forms vary slightly per hackathon; this fills the common
  fields (name, tagline, about, built-with, try-it links, video) with resilient
  selectors and screenshots so the founder can finish/verify any field the form
  names differently. It never clicks the final Submit.
"""
import json, os, sys, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = json.load(open(ROOT / "tools" / "devpost_submissions.json"))
SHOTS = pathlib.Path("/tmp/devpost_shots"); SHOTS.mkdir(exist_ok=True)
PROFILE = "/tmp/devpost_profile"

def about_text(sub):
    p = sub.get("about_file")
    if p and os.path.exists(p):
        return open(p).read()
    return sub.get("tagline", "")

def parse_args():
    only = None; login_check = False
    for a in sys.argv[1:]:
        if a == "--login-check": login_check = True
        elif a.startswith("--only"):
            only = (a.split("=",1)[1] if "=" in a else sys.argv[sys.argv.index(a)+1]).split(",")
    return only, login_check

def shot(pg, name):
    try: pg.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    except Exception: pass

def is_authed(pg):
    """Authoritative auth check: the public nav shows a 'Log in' link ONLY when
    logged out. Returns True iff genuinely authenticated."""
    pg.goto("https://devpost.com/", wait_until="domcontentloaded", timeout=30000)
    pg.wait_for_timeout(2000)
    if pg.query_selector("a[href*='/users/login'], a.login-link"):
        return False
    return True

def login(ctx):
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    if is_authed(pg):
        return pg  # persistent profile already has a live session
    pg.goto("https://secure.devpost.com/users/login", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(2500)
    email = os.environ["DEVPOST_EMAIL"]; pw = os.environ["DEVPOST_PW"]
    e = pg.query_selector("input[name='user[email]']") or pg.query_selector("input[type=email]")
    p = pg.query_selector("input[type=password]")
    e.fill(email); p.fill(pw)
    btn = pg.query_selector("button:has-text('Log in with email')") or pg.query_selector("input[type=submit]")
    btn.click(); pg.wait_for_timeout(6000)
    shot(pg, "00_after_login")
    if not is_authed(pg):
        body = pg.inner_text("body")
        reason = "invalid email/password" if ("Invalid" in body or "incorrect" in body.lower()) else \
                 "no password set on this account (Google-SSO account needs a password set), or login is CAPTCHA-gated"
        raise SystemExit(f"Login failed: {reason}. Founder must set a Devpost password at https://secure.devpost.com/settings.")
    return pg

def fill_first(pg, selectors, value):
    for s in selectors:
        el = pg.query_selector(s)
        if el and el.is_visible():
            try:
                el.fill(value); return True
            except Exception:
                try: el.click(); pg.keyboard.type(value); return True
                except Exception: pass
    return False

def submit_one(pg, sub):
    key = sub["key"]
    pg.goto(sub["hackathon_url"].rstrip("/") + "/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(3000)
    shot(pg, f"{key}_01_hackathon")
    # Register / join if a button is present (idempotent — ignore if already joined)
    for txt in ["Register", "Join hackathon", "Save my spot"]:
        b = pg.query_selector(f"a:has-text('{txt}'), button:has-text('{txt}')")
        if b and b.is_visible():
            try: b.click(); pg.wait_for_timeout(2500)
            except Exception: pass
            break
    # Go to new-submission page
    pg.goto(sub["hackathon_url"].rstrip("/") + "/submissions/new", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(3000)
    shot(pg, f"{key}_02_new_submission")
    fill_first(pg, ["input[name*='name' i]", "input#software_name", "input[name='submission[name]']"], sub["title"])
    fill_first(pg, ["input[name*='tagline' i]", "textarea[name*='tagline' i]", "input#software_tagline"], sub["tagline"])
    # About / description (rich text — try textarea or contenteditable)
    about = about_text(sub)[:5000]
    if not fill_first(pg, ["textarea[name*='detail' i]", "textarea#software_detail", "textarea"], about):
        ce = pg.query_selector("div[contenteditable=true]")
        if ce:
            ce.click(); pg.keyboard.insert_text(about)
    # Try-it links (repo / hosted / video)
    fill_first(pg, ["input[name*='url' i][placeholder*='http' i]"], sub.get("try_it_url", sub["repo_url"]))
    fill_first(pg, ["input[name*='video' i]", "input[placeholder*='video' i]", "input[placeholder*='YouTube' i]"], sub["video_url"])
    shot(pg, f"{key}_03_filled")
    return f"{key}: draft filled (NOT submitted). Review screenshots in {SHOTS}/{key}_*.png and finish/submit manually."

def main():
    only, login_check = parse_args()
    subs = [s for s in CFG["submissions"] if not only or s["key"] in only]
    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=True,
            viewport={"width":1280,"height":1000},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        pg = login(ctx)
        if login_check:
            pg.goto("https://devpost.com/portfolio", wait_until="domcontentloaded", timeout=30000)
            pg.wait_for_timeout(2500); shot(pg, "login_check")
            print("Login OK — screenshot at", SHOTS / "login_check.png")
        else:
            for s in subs:
                try:
                    results.append(submit_one(pg, s))
                except Exception as ex:
                    results.append(f"{s['key']}: ERROR {type(ex).__name__}: {str(ex)[:120]} (see screenshots)")
        ctx.close()
    print("\n".join(results) if results else "done")

if __name__ == "__main__":
    main()
