#!/usr/bin/env python3
"""audit_targets.py — TARGET AUDIT for the portfolio registry.

Founder 2026-07-25/26: the deepest failure found this session was not a missing evolution loop — it was a
BROKEN TARGET. rogii's `rank1` cell held prose ("rank↑(LB 10.419 v7…)"), goal_loop parsed 10.419 out of it =
our own score, so gap==0 and the loop correctly closed itself as AT_#1 while the real frontier sat at 6.794.

A wrong target silently invalidates every drive, every EV allocation and every ceiling verdict downstream, so
it must be audited continuously — not fixed once. This script finds every class of broken target:

  PROSE_RANK1    rank1 is not a number (a number gets parsed out of prose -> phantom target)
  SELF_REF       rank1 == our best exactly (the target is our own score -> gap 0 -> loop closes)
  BEHIND_US      rank1 is WORSE than our best (nothing to chase, yet the row is live)
  NO_TARGET      leaderboard-type row with no rank1 at all (drives have nothing to aim at)
  STALE_CEILING  status=ceiling/dead while the record itself names a better achievable score
  BAD_DIR        registry dir/ledger points somewhere (near-)empty while the real work lives elsewhere

usage: audit_targets.py [--json] [--fix-dirs]     (read-only by default; --fix-dirs only repoints dir/ledger)
"""
import argparse, json, os, re, sys

CT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(CT)                    # repo root (dacon/)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _registry_atomic import write_registry_atomic  # noqa: E402
REG = os.path.join(CT, "portfolio_registry.tsv")
NUM = re.compile(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$")
NUMIN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def columns():
    cols = []
    if not os.path.exists(REG):
        return cols  # fresh install: no registry yet — an empty board, not a crash
    for l in open(REG):
        if l.startswith("#   ") and l[4:5].isalpha() and len(l.split()) > 1:
            cols.append(l.split()[1])
        elif not l.startswith("#"):
            break
    return cols


def rows():
    cols = columns()
    out = []
    if not os.path.exists(REG):
        return cols, out
    for l in open(REG):
        if l.startswith("#") or not l.strip():
            continue
        f = l.rstrip("\n").split("\t")
        d = {c: (f[i] if i < len(f) else "") for i, c in enumerate(cols)}
        d["_raw"] = f
        out.append(d)
    return cols, out


def better(a, b, direction):
    """is a better than b?"""
    return (a < b) if direction == "min" else (a > b)


def dir_files(p):
    ap = os.path.join(ROOT, p) if p and not p.startswith("/") else p
    if not ap or not os.path.isdir(ap):
        return -1
    try:
        return len(os.listdir(ap))
    except OSError:
        return -1


def sibling_dirs(key):
    """other campaign dirs that look like this competition (fragmentation detector)"""
    camp = os.path.join(CT, "campaigns")
    stem = re.split(r"[-_]", key)[0][:6].lower()
    out = []
    if os.path.isdir(camp):
        for d in os.listdir(camp):
            if stem and stem in d.lower():
                out.append((os.path.join("competitions/control_tower/campaigns", d),
                            dir_files(os.path.join("competitions/control_tower/campaigns", d))))
    return sorted(out, key=lambda x: -x[1])


def record_text(r):
    """the competition's own record — used to spot a documented better score than a 'ceiling' claim"""
    for cand in (r.get("ledger", ""), os.path.join(r.get("dir", ""), "WORKLOG.md"),
                 os.path.join(r.get("dir", ""), "RECON.md")):
        if not cand:
            continue
        ap = os.path.join(ROOT, cand) if not cand.startswith("/") else cand
        if os.path.isfile(ap):
            try:
                return open(ap, errors="ignore").read()[:60000]
            except OSError:
                pass
    return ""


def audit():
    cols, rs = rows()
    findings = []
    for r in rs:
        key = r.get("key", "")
        if not key or key == "key":
            continue
        status = (r.get("status") or "").strip()
        if status in ("lapsed", "settled", "dropped"):
            continue
        best_s, r1_s = (r.get("best") or "").strip(), (r.get("rank1") or "").strip()
        direction = (r.get("direction") or "").strip() or "max"
        metric = (r.get("metric") or "").strip()
        judged = metric in ("n/a", "", "-") or (best_s in ("-", "") and r1_s in ("-", ""))
        F = lambda sev, code, msg, fix="": findings.append(
            {"sev": sev, "code": code, "key": key, "msg": msg, "fix": fix, "status": status})

        # --- OUR OWN score integrity (a polluted `best` silently zeroes this row's EV) ---
        if best_s and best_s != "-" and not NUM.match(best_s):
            m = NUMIN.search(best_s)
            F("HIGH", "PROSE_BEST",
              f"best holds a non-numeric value {best_s!r} → EV/gap math silently fails (parsed: {m.group(0) if m else 'none'})",
              "keep `best` strictly numeric; put qualifiers (val/LB/pending) in progress")

        # --- target integrity ---
        if r1_s and r1_s != "-" and not NUM.match(r1_s):
            m = NUMIN.search(r1_s)
            phantom = m.group(0) if m else "none"
            F("CRITICAL", "PROSE_RANK1",
              f"rank1 holds prose → a phantom target '{phantom}' gets parsed from it: {r1_s[:60]!r}",
              "put the real #1 score in rank1; move the prose to progress")
        elif not judged and (not r1_s or r1_s == "-"):
            F("HIGH", "NO_TARGET", "leaderboard-type row has no rank1 — drives have nothing to aim at",
              "fetch the current #1 from the leaderboard and record it")
        elif NUM.match(r1_s) and NUM.match(best_s or ""):
            b, r1 = float(best_s), float(r1_s)
            if abs(b - r1) < 1e-12:
                F("CRITICAL", "SELF_REF", f"rank1 == our best ({best_s}) → gap 0 → the loop closes itself as AT_#1",
                  "record the ACTUAL leaderboard #1, not our own score")
            elif better(b, r1, direction):
                F("MEDIUM", "BEHIND_US", f"rank1 ({r1_s}) is worse than our best ({best_s}) — target already passed",
                  "refresh rank1 from the live leaderboard (or settle the row)")

        # --- stale ceiling vs the record's own numbers ---
        if status in ("ceiling", "dead", "closed"):
            txt = record_text(r)
            if txt and NUM.match(best_s or ""):
                b = float(best_s)
                cands = [float(x) for x in NUMIN.findall(txt)[:4000]]
                cands = [c for c in cands if 0 < abs(c) < 1e7]
                betters = [c for c in cands if better(c, b, direction)]
                if betters:
                    edge = min(betters) if direction == "min" else max(betters)
                    F("HIGH", "STALE_CEILING",
                      f"status={status} but its own record names a better score ({edge:g} vs our {best_s})",
                      "reopen (dead-verdict override) or document why that score is unreachable")

        # --- fragmentation: registry points at an (almost) empty dir ---
        n = dir_files(r.get("dir", ""))
        sib = sibling_dirs(key)
        if n >= 0 and sib and sib[0][1] > max(n * 3, n + 10) and sib[0][0].rstrip("/") != (r.get("dir") or "").rstrip("/"):
            F("HIGH", "BAD_DIR",
              f"dir '{r.get('dir')}' has {n} files but '{sib[0][0]}' has {sib[0][1]} — the real work is elsewhere",
              f"repoint dir/ledger to {sib[0][0]}")
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda f: (order.get(f["sev"], 3), f["key"]))
    return cols, rs, findings


def fix_dirs(cols, rs, findings):
    """The only auto-fix: repoint dir/ledger at the directory that actually holds the work. Target numbers are
    NEVER auto-written — a target is an external fact and must be fetched/verified, not guessed."""
    changed = 0
    lines = open(REG).read().split("\n")
    for f in findings:
        if f["code"] != "BAD_DIR":
            continue
        newdir = f["fix"].split("repoint dir/ledger to ", 1)[-1].strip()
        for i, l in enumerate(lines):
            if l.startswith(f["key"] + "\t"):
                cell = l.split("\t")
                di, li = cols.index("dir"), cols.index("ledger")
                cell[di] = newdir
                wl = os.path.join(ROOT, newdir, "WORKLOG.md")
                cell[li] = os.path.join(newdir, "WORKLOG.md") if os.path.isfile(wl) else newdir + "/"
                lines[i] = "\t".join(cell)
                changed += 1
                break
    if changed:
        write_registry_atomic(REG, "\n".join(lines))
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-dirs", action="store_true", help="auto-repoint dir/ledger only (never targets)")
    a = ap.parse_args()
    cols, rs, findings = audit()
    if a.json:
        print(json.dumps(findings, ensure_ascii=False, indent=1))
        sys.exit(0)
    print(f"== TARGET AUDIT — {len(rs)} registry rows, {len(findings)} finding(s) ==")
    print("   (a broken target silently invalidates every drive, EV ranking and ceiling verdict below it)")
    for f in findings:
        print(f"  [{f['sev']:<8}] {f['code']:<13} {f['key']}")
        print(f"      {f['msg']}")
        if f["fix"]:
            print(f"      → fix: {f['fix']}")
    if a.fix_dirs:
        n = fix_dirs(cols, rs, findings)
        print(f"== auto-fixed dir/ledger on {n} row(s); target numbers left untouched (they need external verification) ==")
    crit = sum(1 for f in findings if f["sev"] == "CRITICAL")
    print(f"== CRITICAL={crit} · HIGH={sum(1 for f in findings if f['sev']=='HIGH')} · "
          f"MEDIUM={sum(1 for f in findings if f['sev']=='MEDIUM')} ==")
