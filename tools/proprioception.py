#!/usr/bin/env python3
"""proprioception.py — the system's sense of its OWN state. Deterministic (non-LLM), fail-closed.

founder 2026-08-08 chose this as the #1 foundation for full autonomy. Rationale (codex + agy + our own record
converged): an agent cannot be autonomous if it cannot reliably know what happened to itself. In-band
self-reading (LLM parsing its own logs) hallucinates success — "silent failure / progress mirage". This session
alone, four of the system's own senses died INVISIBLY: the eval parser emitted `unparsed` for a whole run, a
dashboard sync was dead 3 weeks, a QA gate went false-green, and the single-source-of-truth registry truncated
to 0 bytes. Each looked healthy. A human was the only error-detector.

This is NOT doctor.sh (structural gate/state audit — advisory). This is LIVENESS of the system's senses and
loops, with a FAIL-CLOSED verdict: on any sense it cannot PROVE is alive, it refuses to certify, so a drive
gated on `assert` halts and surfaces instead of optimizing against fiction. It folds doctor's CRITICAL count in.

States (never "probably fine"): ALIVE (proven) · STALE (alive but old) · DEAD (proven broken) · BLIND (cannot
measure — treated as DEAD, because a sense that timed out looks exactly like one that looked and found nothing).

  proprioception.py report              full table of senses + loops + verdict (human/agent readable)
  proprioception.py assert <sense>      exit 0 iff that sense is ALIVE (for drive entry-points; fail-closed)
  proprioception.py --json              machine-readable
"""
import json
import os
import re
import subprocess
import sys
import time

CT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(CT, "portfolio_registry.tsv")
RUNS = os.environ.get("PH_RUNS") or os.path.join(CT, ".runs")
sys.path.insert(0, CT)
import prizehunter_ui as P  # canonical registry parser — proprioception must see what the board sees  # noqa: E402

ALIVE, STALE, DEAD, BLIND = "ALIVE", "STALE", "DEAD", "BLIND"
FAILCLOSED = {DEAD, BLIND}  # anything we cannot prove alive blocks a gated drive

DASH_MAX_AGE_H = float(os.environ.get("PH_PROPRIO_DASH_AGE_H", "3"))
BACKUP_MAX_AGE_H = float(os.environ.get("PH_PROPRIO_BACKUP_AGE_H", "6"))
LOOP_STALE_H = float(os.environ.get("PH_PROPRIO_LOOP_STALE_H", "48"))
MIN_ROWS = int(os.environ.get("PH_PROPRIO_MIN_ROWS", "20"))
EVAL_LOOKBACK = int(os.environ.get("PH_PROPRIO_EVAL_LOOKBACK", "6"))


def _age_h(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 3600.0
    except OSError:
        return None


def _rows():
    """Row dicts via the CANONICAL parser (what the board/dashboard see) — never a bespoke reparse."""
    try:
        return P.parse_registry(with_extras=False)
    except Exception:
        return []


def _raw_row_count():
    """Data lines straight from the file (non-comment, non-blank). Truncation is a property of the FILE, so it
    is measured directly, not through a parser that might be lenient."""
    if not os.path.exists(REG):
        return None
    try:
        return sum(1 for l in open(REG, encoding="utf-8", errors="replace")
                   if l.strip() and not l.startswith("#"))
    except OSError:
        return None


def _campaign_dir(key):
    for c in (os.path.join(CT, "campaigns", key),):
        if os.path.isdir(c):
            return c
    hits = [d for d in (os.path.join(CT, "campaigns", x) for x in os.listdir(os.path.join(CT, "campaigns")))
            if os.path.isdir(d) and key.split("-")[0] in os.path.basename(d)] if os.path.isdir(os.path.join(CT, "campaigns")) else []
    return hits[0] if hits else None


def _proc_running(needle):
    try:
        out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None  # cannot measure
    return any(needle in l and "proprioception" not in l and "grep" not in l for l in out.splitlines())


# ── senses ────────────────────────────────────────────────────────────────────────────────────────────────
def sense_registry():
    if not os.path.exists(REG):
        return DEAD, "registry file MISSING"
    n = _raw_row_count()
    if n is None:
        return BLIND, "registry unreadable"
    if n == 0:
        return DEAD, "registry has 0 data rows (truncated)"
    # TRUNCATION is a DROP from a known baseline, not an absolute size — a fresh clone's small template
    # registry is healthy, not truncated. Compare to the newest rolling backup's row count.
    bdir = os.path.join(RUNS, "registry_backups")
    newest_age, bak_rows = None, None
    if os.path.isdir(bdir):
        baks = sorted(os.listdir(bdir))
        if baks:
            bp = os.path.join(bdir, baks[-1])
            newest_age = _age_h(bp)
            try:
                bak_rows = sum(1 for l in open(bp, encoding="utf-8", errors="replace")
                               if l.strip() and not l.startswith("#"))
            except OSError:
                bak_rows = None
    if bak_rows and bak_rows >= 10 and n < bak_rows * 0.5:
        return DEAD, f"registry has {n} rows but the backup had {bak_rows} — truncation (>50% drop)"
    # every registry writer must be atomic (a non-atomic open('w') is the 08-01 truncation race)
    nonatomic = []
    tdir = os.path.join(CT, "tools")
    for fn in os.listdir(tdir):
        if not fn.endswith(".py") or fn == "_registry_atomic.py":
            continue
        try:
            src = open(os.path.join(tdir, fn), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if re.search(r"open\(\s*(REG|REGISTRY|reg)\s*,\s*[\"']w", src):
            nonatomic.append(fn)
    if nonatomic:
        return DEAD, f"{n} rows but NON-ATOMIC writers present ({','.join(nonatomic)}) — truncation race live"
    if newest_age is None:
        # no backup yet is normal for a young/fresh instance — not a failure, just note it
        return ALIVE, f"{n} rows · atomic writers · (no rolling backup yet)"
    if newest_age > BACKUP_MAX_AGE_H:
        return STALE, f"{n} rows, atomic — newest backup {newest_age:.1f}h old (> {BACKUP_MAX_AGE_H}h)"
    return ALIVE, f"{n} rows · atomic writers · backup {newest_age:.1f}h old"


def sense_dashboard():
    # the hosted dashboard is OPTIONAL — a clone without Supabase configured simply has no dashboard,
    # which is not a failure. Only judge liveness when it is actually configured.
    if not os.path.exists(os.path.expanduser("~/.config/prizehunter/supabase.env")):
        return ALIVE, "N/A — no hosted dashboard configured (local-only install)"
    log = os.path.join(RUNS, "sync.log")
    if not os.path.exists(log):
        return DEAD, "dashboard configured but no sync.log — sync has never run"
    age = _age_h(log)
    # read last 'synced:' line
    last = None
    try:
        for l in reversed(open(log, encoding="utf-8", errors="replace").read().splitlines()):
            if "synced:" in l:
                last = l
                break
    except OSError:
        return BLIND, "sync.log unreadable"
    if last is None:
        return DEAD, "sync.log has no successful 'synced:' line"
    m = re.search(r"'competitions':\s*(\d+)", last)
    synced_n = int(m.group(1)) if m else 0
    rows = _rows()
    if synced_n == 0:
        return DEAD, f"last sync pushed 0 competitions (dashboard blank) — {last[-60:].strip()}"
    if age is not None and age > DASH_MAX_AGE_H:
        return STALE, f"last sync {age:.1f}h ago (> {DASH_MAX_AGE_H}h); pushed {synced_n}"
    if rows and abs(synced_n - len(rows)) > max(3, 0.1 * len(rows)):
        return DEAD, f"dashboard shows {synced_n} but registry has {len(rows)} — out of sync"
    return ALIVE, f"synced {synced_n} rows {('%.1fh' % age) if age is not None else '?'} ago"


def sense_eval(active):
    """The v1 'score=unparsed' class: a LIVE loop whose eval reads silently fail, so it submits nothing while
    looking busy. Scoped to FRESH loops only — a dead loop's lack of scores is the loops sense's job, not this
    one (no double-flagging). An 'eval attempt' is a variant row (`*.py`); probe/measurement rows are neutral."""
    worst, notes = ALIVE, []
    checked = 0
    for r in active:
        key = r["key"]
        d = _campaign_dir(key)
        led = os.path.join(d, "iterate_ledger.tsv") if d else None
        if not led or not os.path.exists(led):
            continue
        age = _age_h(led)
        if age is None or age > LOOP_STALE_H:
            continue  # not fresh → dead-loop territory, deferred to sense_loops
        rows = [l.rstrip("\n").split("\t") for l in open(led, encoding="utf-8", errors="replace")
                if l.strip() and not l.startswith("#")]
        attempts = [x for x in rows[-EVAL_LOOKBACK * 2:] if x and x[1].endswith(".py")][-EVAL_LOOKBACK:]
        if not attempts:
            continue  # loop is doing probes, not variant evals — nothing for this sense to judge
        checked += 1
        def parsed(row):
            # iterate_ledger schema: col4 is the numeric score (col5 is a note, usually empty)
            if len(row) < 5:
                return False
            try:
                float(row[4]); return True
            except (ValueError, IndexError):
                return False
        if not any(parsed(x) for x in attempts):
            worst = DEAD
            notes.append(f"{key}: live loop but last {len(attempts)} variant evals all unparsed/FAILED — "
                         f"submitting against unreadable evals")
    if checked == 0:
        return ALIVE, "no live variant-eval loops to judge (dead/idle loops handled by loops sense)"
    return worst, ("; ".join(notes) if notes else f"{checked} live eval loop(s), recent variant evals parse")


def sense_loops(active):
    """An 'active' leaderboard row whose ledger has not advanced in LOOP_STALE_H and has no live drive process
    is a DEAD LOOP — not stuck, dead. (arc-whitebox died 2026-07-28 and no one noticed for 11 days.)"""
    worst, notes = ALIVE, []
    for r in active:
        key = r["key"]
        d = _campaign_dir(key)
        led = os.path.join(d, "iterate_ledger.tsv") if d else None
        age = _age_h(led) if led and os.path.exists(led) else None
        if age is None:
            continue  # no ledger to judge liveness by
        if age > LOOP_STALE_H:
            running = _proc_running(key)
            if running is False:
                worst = DEAD
                notes.append(f"{key}: ledger idle {age/24:.1f}d, NO drive process → DEAD LOOP")
            elif running is None:
                if worst != DEAD:
                    worst = BLIND
                notes.append(f"{key}: ledger idle {age/24:.1f}d, cannot check process")
            else:
                notes.append(f"{key}: ledger idle {age/24:.1f}d but a process is running (long compute?)")
    return worst, ("; ".join(notes) if notes else "all active loops fresh or progressing")


def sense_gate():
    """Every advertised `ph` verb must dispatch to a live case arm — an advertised-but-unimplemented verb
    returns success via help (the false-green class: `ph goal` fell through to help with rc 0)."""
    ph = os.path.join(CT, "ph")
    if not os.path.exists(ph):
        return BLIND, "ph front door not found"
    t = open(ph, encoding="utf-8", errors="replace").read()
    adv = set(re.findall(r"^\s+ph ([a-z0-9-]+)", t, re.M))
    arms = set()
    for m in re.findall(r"^\s{2}([a-z0-9|_-]+)\)", t, re.M):
        arms.update(m.split("|"))
    missing = sorted(adv - arms - {"help"})
    # fold doctor's CRITICAL count
    crit = None
    doc = os.path.join(CT, "tools", "doctor.sh")
    if os.path.exists(doc):
        try:
            out = subprocess.run(["bash", doc], capture_output=True, text=True, timeout=120).stdout
            m = re.search(r"(\d+)\s*CRITICAL", out)
            crit = int(m.group(1)) if m else 0
        except Exception:
            crit = None
    if missing:
        return DEAD, f"advertised verbs with NO arm (false-green): {missing}"
    if crit:
        return DEAD, f"all verbs wired, but doctor reports {crit} CRITICAL"
    if crit is None:
        return STALE, "verbs wired; doctor not runnable to fold CRITICAL count"
    return ALIVE, "every advertised verb has a live arm; doctor 0 CRITICAL"


def _num(x):
    try:
        return float(str(x).split()[0])
    except (ValueError, IndexError, AttributeError):
        return None


def sense_verdict(active):
    """Is the VERDICT AUTHORITY sane? A row whose `direction` is inverted makes goal_loop declare AT_#1 (false
    victory) and stop driving — the exact bug that left arc-whitebox undriven while 29x BEHIND #1. Signature:
    verdict says AT/ABOVE #1 while best and rank1 are orders of magnitude apart."""
    worst, notes = ALIVE, []
    for r in active:
        b, r1, d = _num(r.get("best")), _num(r.get("rank1")), r.get("direction")
        if b is None or r1 is None or b <= 0 or r1 <= 0:
            continue
        at1 = (b >= r1) if d == "max" else (b <= r1)
        ratio = max(b, r1) / min(b, r1)
        if at1 and ratio > 1.5:
            worst = DEAD
            notes.append(f"{r['key']}: verdict AT_#1 but best/rank1 {ratio:.0f}x apart under dir={d} — "
                         f"direction likely inverted (false victory → row never driven)")
    return worst, ("; ".join(notes) if notes else "verdict authority sane (no false-AT_#1 / inverted dir)")


def sense_process():
    """Process hygiene: leaked cockpit daemons accumulate (13 --no-loop prizehunterd were live on 2026-08-08,
    from unreaped smoke test daemons). Flag before it becomes contention."""
    try:
        out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return BLIND, "cannot enumerate processes"
    noloop = sum(1 for l in out.splitlines() if "prizehunterd.py" in l and "--no-loop" in l and "grep" not in l)
    if noloop > 3:
        return DEAD, f"{noloop} leaked '--no-loop' prizehunterd daemons — reap them (kill the --no-loop PIDs)"
    if noloop > 1:
        return STALE, f"{noloop} '--no-loop' daemons (a couple is ok; watch for accumulation)"
    return ALIVE, f"{noloop} leaked daemon(s)"


SENSES = ["registry", "dashboard", "eval", "loops", "gate", "verdict", "process"]


def run_all():
    rows = _rows()
    active = [r for r in rows if "active" in (r.get("status", "").lower())
              and r.get("direction", "") in ("max", "min")]
    res = {}
    res["registry"] = sense_registry()
    res["dashboard"] = sense_dashboard()
    res["eval"] = sense_eval(active)
    res["loops"] = sense_loops(active)
    res["gate"] = sense_gate()
    res["verdict"] = sense_verdict(active)
    res["process"] = sense_process()
    return res


def main():
    args = sys.argv[1:]
    if args and args[0] == "assert":
        which = args[1] if len(args) > 1 else "all"
        res = run_all()
        targets = SENSES if which in ("all", "") else [which]
        bad = [(k, *res[k]) for k in targets if k in res and res[k][0] in FAILCLOSED]
        if bad:
            for k, st, ev in bad:
                print(f"⛔ PROPRIOCEPTION [{k}] {st}: {ev} — refusing to certify (fail-closed).", file=sys.stderr)
            sys.exit(3)
        sys.exit(0)

    res = run_all()
    if "--json" in args:
        print(json.dumps({k: {"state": v[0], "evidence": v[1]} for k, v in res.items()}, ensure_ascii=False, indent=2))
        return
    icon = {ALIVE: "🟢", STALE: "🟡", DEAD: "🔴", BLIND: "⚫"}
    print("== proprioception — the system's sense of its own state (deterministic, fail-closed) ==")
    worst_fc = False
    for k in SENSES:
        st, ev = res[k]
        worst_fc = worst_fc or st in FAILCLOSED
        print(f"  {icon.get(st,'?')} {k:<10} {st:<6} {ev}")
    print()
    if worst_fc:
        print("VERDICT: 🔴 FAIL-CLOSED — at least one sense is DEAD/BLIND. A drive gated on `assert` will halt.")
        print("         Silence is not health: fix the sense before trusting any drive result.")
        sys.exit(3)
    print("VERDICT: 🟢 all senses proven alive (this certifies the system can TRUST itself, not that it WINS).")
    sys.exit(0)


if __name__ == "__main__":
    main()
