#!/usr/bin/env python3
"""discover_contests.py — generic, pluggable discovery for ANY contest platform.

Reads contest_sources.tsv (one row per platform) and extracts contests by anchoring
on each item's DETAIL-LINK regex (robust across sites). Adding a platform = add a
row. The domains the founder named are just examples — this scales to all of them.
Writes candidates_contests.tsv for the ROI scorer (prize_roi.py).

Title is captured from the listing; prize/deadline/category live on detail pages
and are inferred from the title here + fetched by the ROI scorer for top picks.

Usage: discover_contests.py [--platform wevity] [--max N]
"""
import re, os, subprocess, argparse, html

HERE = os.path.dirname(os.path.abspath(__file__))

def fetch(url, render='curl'):
    if render == 'browser':
        # headless Chrome for JS-rendered listings (Kaggle/Devpost/culture/...)
        return subprocess.check_output(
            ['python3', os.path.join(HERE, 'fetch_render.py'), url, '--scroll', '2'],
            text=True, errors='ignore', timeout=120)
    return subprocess.check_output(
        ['curl','-L','--connect-timeout','10','--max-time','30','-sA','Mozilla/5.0',url],
        text=True, errors='ignore')

def parse_source(row, cap):
    page = fetch(row['list_url'], row.get('render', 'curl'))
    rx = re.compile(row['item_re'], re.S)
    seen, items = set(), []
    for m in rx.finditer(page):
        cid, title = m.group(1), html.unescape(re.sub(r'\s+',' ',m.group(2))).strip()
        if cid in seen or len(title) < 6:
            continue
        seen.add(cid)
        items.append({
            'platform': row['platform'], 'id': cid, 'name': title[:90],
            'url': row['base'].replace('{id}', cid),
        })
        if len(items) >= cap:
            break
    return items

def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(__file__)
    ap.add_argument('--sources', default=os.path.join(here,'..','contest_sources.tsv'))
    ap.add_argument('--platform', default='')
    ap.add_argument('--max', type=int, default=60)
    ap.add_argument('--out', default=os.path.join(here,'..','candidates_contests.tsv'))
    a = ap.parse_args()

    rows, hdr = [], None
    for line in open(a.sources):
        line = line.rstrip('\n')
        if not line or line.startswith('#'): continue
        c = line.split('\t')
        if hdr is None: hdr = c; continue
        r = dict(zip(hdr, c))
        if a.platform and r['platform'] != a.platform: continue
        rows.append(r)

    allitems, skipped = [], []
    for r in rows:
        try:
            it = parse_source(r, a.max)
            allitems += it if it else []
            if not it: skipped.append(f"{r['platform']}(0)")
        except Exception as e:
            skipped.append(f"{r['platform']}({e})")

    cols = ['platform','id','name','url']
    with open(a.out,'w') as o:
        o.write('\t'.join(cols)+'\n')
        for it in allitems:
            o.write('\t'.join(it.get(k,'') for k in cols)+'\n')
    print(a.out)
    print(f"discovered={len(allitems)} from {len(rows)} source(s); skipped:{skipped or ' none'}")

if __name__ == '__main__':
    main()
