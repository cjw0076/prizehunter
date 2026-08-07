#!/usr/bin/env python3
"""lb_sensor.py — CONTINUOUS leaderboard sensor with provenance. Answers "is our target still the target?"

founder 2026-07-27: "leaderboard 형은 계속 순위가 뒤바뀌는데. 실제로 확인하는게 필요해. 그래서 네가 개선을
못하고있는건가?"

Measured answer: partly yes, and the mechanism is allocation, not effort.
  · rogii  #1 moved 4.859 → 4.679 inside one day (and #3 changed too).
  · arc    our recorded #1 was 6.93e-8; the live board read 2.46e-8 — our target was 2.8x stale, because a
           new participant jumped 199 places with 80 entries.
  · of 10 live numeric rows, 3 carried NO date at all (scpc, playground-s6e7, kaggle-autonomous-agent-beta),
    and only 4 were covered by any auto-refresh.
A stale rank1 does not slow the work down — it points the work at the wrong row. `goal_loop`'s verdicts
(AT_#1 / PUSH) and the EV allocator are both functions of rank1, so a target that has drifted makes the
system confidently spend on the wrong competition, and worse: a row that reads "1.00x, tied with #1" tells
the system to stop pushing at exactly the moment it has fallen behind.

So: read every live row's board from its own platform, stamp WHEN it was read, and record the movement.

    lb_sensor.py                 read every live row that has a reader; print the movement table
    lb_sensor.py --sync          also write rank1 (+ rank1_at provenance) back into the registry
    lb_sensor.py --key K         one row only
    lb_sensor.py --sources       show the key → platform/slug map and which rows have NO reader

Readers: kaggle (CLI), aicrowd (the logged-in browser via council/hub.py), numerai (public GraphQL).
Rows with no reader are printed as UNREADABLE — never silently skipped, because a silent gap is how a
target goes stale for nine days.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(CT))
REG = os.path.join(CT, "portfolio_registry.tsv")
sys.path.insert(0, HERE)
from _registry_atomic import write_registry_atomic
SOURCES = os.path.join(CT, "lb_sources.tsv")
HIST = os.path.join(CT, ".runs", "lb_history.tsv")
KAGGLE = os.path.expanduser("~/miniconda3/bin/kaggle")
HUB = os.path.join(ROOT, "council", "hub.py")
DEAD = ("lapsed", "settled", "dropped", "closed")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_registry():
    cols = []
    for line in open(REG, encoding="utf-8", errors="replace"):
        if line.startswith("#   ") and line[4:5].isalpha() and len(line.split()) > 1:
            cols.append(line.split()[1])
        elif not line.startswith("#"):
            break
    rows = []
    for line in open(REG, encoding="utf-8", errors="replace"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < len(cols):
            f += [""] * (len(cols) - len(f))
        rows.append(dict(zip(cols, f)))
    return cols, rows


def load_sources():
    """key -> (platform, slug). Seeded on first run; edit lb_sources.tsv to add a row's reader."""
    if not os.path.exists(SOURCES):
        seed = [
            ("playground-s6e7", "kaggle", "playground-series-s6e7"),
            ("kaggle-autonomous-agent-beta", "kaggle", "autonomous-agent-prediction-beta"),
            ("rogii-wellbore-geology", "kaggle", "rogii-wellbore-geology-prediction"),
            ("arc-prize-2026-arc-agi-2", "kaggle", "arc-prize-2026"),
            ("arc-whitebox-2026", "aicrowd", "arc-white-box-estimation-challenge-2026"),
            ("numerai-main", "numerai", "tournament-8"),
        ]
        with open(SOURCES, "w", encoding="utf-8") as fh:
            fh.write("# key\tplatform\tslug   — the reader map for lb_sensor.py.\n")
            fh.write("# A registry key is NOT a platform slug (that mismatch produced a wrong RMSE once),\n")
            fh.write("# so the mapping is explicit and reviewable rather than guessed from the key.\n")
            for k, p, s in seed:
                fh.write("%s\t%s\t%s\n" % (k, p, s))
    out = {}
    for line in open(SOURCES, encoding="utf-8", errors="replace"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) >= 3:
            out[f[0]] = (f[1], f[2])
    return out


# ---------- platform readers: each returns (top1, our_best, our_rank) with None where unknown ----------
def read_kaggle(slug, direction):
    top = ours = rank = None
    try:
        p = subprocess.run([KAGGLE, "competitions", "leaderboard", "-c", slug, "-s", "--csv"],
                           capture_output=True, text=True, timeout=120)
        for line in p.stdout.replace("\r", "").splitlines()[1:]:
            cells = line.split(",")
            for c in reversed(cells):
                if re.fullmatch(r"-?\d+\.\d+", c.strip()):
                    top = float(c)
                    break
            if top is not None:
                break
    except Exception:
        pass
    try:
        p = subprocess.run([KAGGLE, "competitions", "submissions", "-c", slug, "-v"],
                           capture_output=True, text=True, timeout=120)
        vals = []
        for line in p.stdout.replace("\r", "").splitlines()[1:]:
            for c in line.split(","):
                if re.fullmatch(r"-?\d+\.\d+", c.strip()):
                    vals.append(float(c))
                    break
        if vals:
            ours = min(vals) if direction == "min" else max(vals)
    except Exception:
        pass
    return top, ours, rank


def read_aicrowd(slug, direction):
    top = ours = rank = None
    if not os.path.exists(HUB):
        return top, ours, rank
    js = ("(()=>{const t=document.body.innerText.replace(/[\\u2212\\u2013\\u2014]/g,'-');"
          "const m=t.match(/ADJUSTED SCORE\\s*([0-9.eE+-]+)/);"
          "const r=t.match(/You are ranked #(\\d+)/);"
          "return JSON.stringify({top:(m&&m[1])||'',rank:(r&&r[1])||''})})()")
    try:
        p = subprocess.run(["python3", HUB, "browse", "eval",
                            "https://www.aicrowd.com/challenges/%s/leaderboards" % slug, js],
                           capture_output=True, text=True, timeout=300)
        m = re.search(r'"result":\s*"(.*)"\s*\n?\}', p.stdout, re.S)
        if m:
            inner = json.loads(json.loads('"%s"' % m.group(1)))
            if inner.get("top"):
                top = float(inner["top"])
            if inner.get("rank"):
                rank = int(inner["rank"])
    except Exception:
        pass
    return top, ours, rank


def read_numerai(slug, direction):
    """payout proxy 0.75*CORR + 2.25*MMC on the live board, same formula our own record uses."""
    try:
        import urllib.request
        q = json.dumps({"query": "query { v2Leaderboard(limit: 1) { username corr20V2Rep mmcRep } }"}).encode()
        req = urllib.request.Request("https://api-tournament.numer.ai/", data=q, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "prizehunter-lb-sensor/1.0"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        r = d["data"]["v2Leaderboard"][0]
        return 0.75 * (r.get("corr20V2Rep") or 0) + 2.25 * (r.get("mmcRep") or 0), None, None
    except Exception as e:
        # print the reason instead of hiding it: a silent read-failure is indistinguishable from "unchanged",
        # which is exactly how a target stays stale while the dashboard looks healthy.
        print("      numerai read error: %s" % str(e)[:120])
        return None, None, None


READERS = {"kaggle": read_kaggle, "aicrowd": read_aicrowd, "numerai": read_numerai}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true", help="write rank1 + rank1_at back into the registry")
    ap.add_argument("--key", default=None)
    ap.add_argument("--sources", action="store_true")
    a = ap.parse_args()

    cols, rows = read_registry()
    src = load_sources()
    if a.sources:
        print("== reader map (lb_sources.tsv) ==")
        for k, (p, s) in sorted(src.items()):
            print("  %-30s %-9s %s" % (k, p, s))
        missing = [r["key"] for r in rows
                   if (r.get("status") or "") not in DEAD and r["key"] not in src
                   and re.fullmatch(r"-?\d*\.?\d+(e-?\d+)?", (r.get("rank1") or "").strip() or "x")]
        print("\n== live numeric rows with NO reader (these go stale silently) ==")
        for k in missing:
            print("  %s" % k)
        return 0

    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    if not os.path.exists(HIST):
        open(HIST, "w", encoding="utf-8").write("# at\tkey\tplatform\ttop1\tprev_rank1\tour_best\tour_rank\tmoved\n")

    print("== leaderboard sensor %s ==" % now())
    print("  %-28s %-8s %14s %14s %9s %s" % ("key", "platform", "live #1", "our rank1", "moved", "our rank"))
    updates = []
    for r in rows:
        if (r.get("status") or "") in DEAD:
            continue
        k = r["key"]
        if a.key and k != a.key:
            continue
        if k not in src:
            try:
                float((r.get("rank1") or "").strip())
                print("  %-28s %-8s %14s %14s   UNREADABLE (no reader in lb_sources.tsv)"
                      % (k[:28], "-", "-", r.get("rank1")))
            except ValueError:
                pass
            continue
        plat, slug = src[k]
        if plat == "skip":
            print("  %-28s %-8s   owned by another tracker (no double-tracking): %s" % (k[:28], plat, slug[:60]))
            continue
        if plat == "todo":
            print("  %-28s %-8s   ⚠ ADAPTER MISSING — this target CANNOT go stale silently, it is stale by "
                  "construction: %s" % (k[:28], plat, slug[:70]))
            continue
        reader = READERS.get(plat)
        if not reader:
            print("  %-28s %-8s   no reader implemented for this platform" % (k[:28], plat))
            continue
        direction = (r.get("direction") or "min").strip()
        top, ours, rank = reader(slug, direction)
        try:
            prev = float((r.get("rank1") or "").strip())
        except ValueError:
            prev = None
        moved = ""
        if top is not None and prev is not None and prev:
            rel = (top - prev) / abs(prev)
            if abs(rel) > 1e-9:
                harder = (top < prev) if direction == "min" else (top > prev)
                moved = "%+.2f%% %s" % (100 * rel, "HARDER" if harder else "easier")
        print("  %-28s %-8s %14s %14s %9s %s"
              % (k[:28], plat, ("%.6g" % top) if top is not None else "read-failed",
                 ("%.6g" % prev) if prev is not None else "-", moved or "same",
                 ("#%d" % rank) if rank else ""))
        open(HIST, "a", encoding="utf-8").write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
            now(), k, plat, top if top is not None else "", prev if prev is not None else "",
            ours if ours is not None else "", rank or "", moved))
        if top is not None and (prev is None or abs(top - prev) > 1e-12):
            updates.append((k, prev, top))

    if not a.sync:
        print("\n  %d row(s) have a live #1 differing from our recorded target. Run with --sync to write them"
              " (and stamp rank1_at, so 'when was this measured' stops being unanswerable)." % len(updates))
        return 0

    # write back: rank1 + a rank1_at provenance column appended to the schema
    lines = open(REG, encoding="utf-8").read().split("\n")
    if "rank1_at" not in cols:
        for i, l in enumerate(lines):
            if l.startswith("#   next_lever"):
                lines.insert(i + 1, "#   rank1_at       UTC timestamp when rank1 was last read from the live board")
                break
        cols = cols + ["rank1_at"]
    i_r1, i_at = cols.index("rank1"), cols.index("rank1_at")
    changed = 0
    for i, l in enumerate(lines):
        if l.startswith("#") or not l.strip():
            continue
        f = l.split("\t")
        if not f:
            continue
        hit = [u for u in updates if u[0] == f[0]]
        if not hit:
            continue
        while len(f) <= max(i_r1, i_at):
            f.append("")
        f[i_r1] = "%.12g" % hit[0][2]
        f[i_at] = now()
        lines[i] = "\t".join(f)
        changed += 1
        print("  ✓ %-28s rank1 %s → %.6g (stamped)" % (f[0][:28], hit[0][1], hit[0][2]))
    write_registry_atomic(REG, "\n".join(lines))
    print("  synced %d row(s) · history: %s" % (changed, HIST))
    return 0


if __name__ == "__main__":
    sys.exit(main())
