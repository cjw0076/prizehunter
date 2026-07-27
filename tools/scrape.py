#!/home/user/miniconda3/envs/dacon_vlm/bin/python
"""scrape — universal agent web-scraper (Scrapling StealthyFetcher).

Any agent can call this to read SPA / anti-bot / JS-rendered pages that plain
WebFetch/curl cannot, WITHOUT a login, Google session, or browser-auth gate.
Env (chromium path, no-sandbox) is baked in — agents need to know nothing.

USAGE (run with any python; it re-execs into the scrapling env if needed):
  scrape.py <url>                         # full page text
  scrape.py <url> --links [PATTERN]       # all links (href filtered by PATTERN)
  scrape.py <url> --css "SELECTOR"        # text of CSS matches (::text auto)
  scrape.py <url> --css "a.item" --attr href
  scrape.py <url> --xpath "//h2"
  scrape.py <url> --html                  # raw html (truncated unless --full)
  scrape.py <url> --json                  # structured JSON out
  scrape.py <url> --screenshot out.png    # dynamic fetcher screenshot
Options: --dynamic (full browser vs stealth-http) · --full (no truncation) · --timeout N
"""
import os, sys, json, argparse

SCRAPLING_PY = os.path.expanduser("~/miniconda3/envs/dacon_vlm/bin/python")

def _ensure_env():
    os.environ.setdefault("GSTACK_CHROMIUM_NO_SANDBOX", "1")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/home/user/.cache/ms-playwright")
    # re-exec into the env that has scrapling, if this python lacks it
    try:
        import scrapling  # noqa
    except ImportError:
        if os.path.abspath(sys.executable) != os.path.abspath(SCRAPLING_PY) and os.path.exists(SCRAPLING_PY):
            os.execv(SCRAPLING_PY, [SCRAPLING_PY] + sys.argv)
        sys.exit("scrapling not installed and env python missing; pip install 'scrapling[fetchers]'")

def main():
    ap = argparse.ArgumentParser(description="universal agent scraper (Scrapling)")
    ap.add_argument("url")
    ap.add_argument("--links", nargs="?", const="", help="extract links; optional href substring filter")
    ap.add_argument("--css"); ap.add_argument("--xpath"); ap.add_argument("--attr")
    ap.add_argument("--text", action="store_true"); ap.add_argument("--html", action="store_true")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--screenshot")
    ap.add_argument("--dynamic", action="store_true"); ap.add_argument("--full", action="store_true")
    ap.add_argument("--timeout", type=int, default=60000)
    a = ap.parse_args()

    _ensure_env()
    from scrapling.fetchers import StealthyFetcher, DynamicFetcher
    F = DynamicFetcher if a.dynamic else StealthyFetcher
    try: F.adaptive = True
    except Exception: pass
    kw = dict(headless=True, network_idle=True)
    if a.screenshot:
        kw["screenshot"] = a.screenshot if a.dynamic else None
    page = F.fetch(a.url, **{k: v for k, v in kw.items() if v is not None})

    out = {"url": a.url, "status": getattr(page, "status", None)}
    if a.links is not None:
        res = []
        for el in page.css("a"):
            href = el.attrib.get("href", "")
            if a.links and a.links not in href: continue
            txt = el.get_all_text().strip().replace("\n", " ")
            if href: res.append({"text": txt[:100], "href": href})
        # dedup by href
        seen, ded = set(), []
        for r in res:
            if r["href"] in seen: continue
            seen.add(r["href"]); ded.append(r)
        out["links"] = ded
    elif a.css or a.xpath:
        els = page.css(a.css) if a.css else page.xpath(a.xpath)
        vals = []
        for el in els:
            vals.append(el.attrib.get(a.attr, "") if a.attr else el.get_all_text().strip())
        out["matches"] = [v for v in vals if v]
    elif a.html:
        h = page.html_content if hasattr(page, "html_content") else str(page)
        out["html"] = h if a.full else h[:4000]
    else:
        t = page.get_all_text()
        out["text"] = t if a.full else t[:6000]
    if a.screenshot: out["screenshot"] = a.screenshot

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if "links" in out:
            for l in out["links"]: print(f"{l['href']}\t{l['text']}")
        elif "matches" in out:
            for m in out["matches"]: print(m)
        else:
            print(out.get("text") or out.get("html") or f"status={out['status']}")

if __name__ == "__main__":
    main()
