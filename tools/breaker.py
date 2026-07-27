#!/usr/bin/env python3
"""breaker.py — FRAMING CIRCUIT BREAKER. Detect that the current framing is exhausted and force a reframe.

The failure this exists to prevent (measured): for six weeks the arc-whitebox campaign produced eight variants
of one idea — Gaussian moment closure with different corrections — and the leaderboard never moved. Nothing in
the system could notice that the *framing* was the problem rather than the parameters. The break came from a
heterogeneous consult a HUMAN asked for. That is the single most load-bearing human input measured today, so it
is the one that most needs to become mechanical.

agy's construction, adopted: track improvement per attempt; after K consecutive attempts whose relative gain is
below a threshold, emit FRAMING_EXHAUSTED and force a consult that demands ORTHOGONAL formulations rather than
hyperparameter tweaks. The distinction matters: "more samples / different weight" is inside the framing;
"the closure itself is wrong, use quadrature" is outside it.

    breaker.py check <ledger.tsv> [--k 5] [--eps 0.01] [--scale local|graded]
        exit 0  = keep going (still improving)
        exit 10 = FRAMING_EXHAUSTED (caller must reframe, not tune)
    breaker.py selftest      prove it trips on a flat series and does not trip on an improving one

Why exit codes rather than a printed word: a caller that greps prose will silently mis-read it one day, which
is exactly the class of bug `contract.py` exists for.
"""
import argparse
import os
import sys

EXIT_EXHAUSTED = 10


def series_from_ledger(path, scale):
    """Ordered list of (label, score) for one scale. Ledger schema: ts, variant, scale, split, score, ..."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 5 or f[2] != scale or not f[4].strip():
            continue
        try:
            out.append((f[1], float(f[4])))
        except ValueError:
            continue
    return out


def verdict(series, k, eps, direction="min"):
    """Returns (exhausted, detail). A round counts as 'no progress' when the running best improves by less
    than eps in RELATIVE terms — absolute thresholds are useless across metrics that live at 1e-7 and 0.95."""
    if len(series) < k + 1:
        return False, "only %d attempt(s) on record; need %d to judge exhaustion" % (len(series), k + 1)
    best = series[0][1]
    flat = 0
    worst_streak = 0
    for _, s in series[1:]:
        improved = (s < best) if direction == "min" else (s > best)
        rel = abs(s - best) / abs(best) if best else 0.0
        if improved and rel >= eps:
            best = s
            flat = 0
        else:
            if improved:
                best = s
            flat += 1
            worst_streak = max(worst_streak, flat)
    return (flat >= k,
            "%d consecutive attempt(s) without a >=%.1f%% improvement (longest streak %d, best %.6g)"
            % (flat, 100 * eps, worst_streak, best))


REFRAME_PROMPT = """FRAMING_EXHAUSTED — %s

Do NOT propose another parameter setting, weight, sample count or blend of what we already have. Those are
inside the framing that just failed %d times in a row.

Give me ORTHOGONAL formulations: a different mathematical object, a different estimator class, a different
reading of what the metric rewards, or a claim that our target/harness reading is itself wrong. For each:
name it, say why it escapes the failure mode above, give its cost scaling, and state the measurement that
would kill it. Rank them by expected score movement per unit of compute.
"""


def selftest():
    fails = 0
    flat = [("v%d" % i, 1.0 - 0.0005 * i) for i in range(8)]          # improving by 0.05% -> below eps
    ex, why = verdict(flat, 5, 0.01, "min")
    print("  %s flat/near-flat series trips the breaker (%s)" % ("✓" if ex else "✗", why))
    fails += not ex
    good = [("v%d" % i, 1.0 / (2 ** i)) for i in range(8)]            # halving each time
    ex, why = verdict(good, 5, 0.01, "min")
    print("  %s genuinely improving series does NOT trip (%s)" % ("✓" if not ex else "✗", why))
    fails += ex
    ex, why = verdict([("a", 1.0)], 5, 0.01, "min")
    print("  %s too-short history does not trip (%s)" % ("✓" if not ex else "✗", why))
    fails += ex
    mixed = [("a", 1.0), ("b", 0.5), ("c", 0.499), ("d", 0.4985), ("e", 0.4984), ("f", 0.4983), ("g", 0.4982)]
    ex, why = verdict(mixed, 5, 0.01, "min")
    print("  %s one real gain then five stalls trips (%s)" % ("✓" if ex else "✗", why))
    fails += not ex
    print("  selftest %s" % ("PASSED" if not fails else "FAILED"))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "selftest"])
    ap.add_argument("ledger", nargs="?")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--eps", type=float, default=0.01)
    ap.add_argument("--scale", default="graded")
    ap.add_argument("--direction", default="min")
    ap.add_argument("--print-prompt", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if not a.ledger:
        print("need a ledger path")
        return 2
    s = series_from_ledger(a.ledger, a.scale)
    ex, why = verdict(s, a.k, a.eps, a.direction)
    print("breaker[%s scale=%s k=%d eps=%.1f%%]: %s" % (
        "EXHAUSTED" if ex else "ok", a.scale, a.k, 100 * a.eps, why))
    if ex and a.print_prompt:
        print("---REFRAME---")
        print(REFRAME_PROMPT % (why, a.k))
    return EXIT_EXHAUSTED if ex else 0


if __name__ == "__main__":
    sys.exit(main())
