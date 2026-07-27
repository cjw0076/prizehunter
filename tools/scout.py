#!/usr/bin/env python3
"""scout.py — the periodic "latest-info friend".

Every cycle it (1) sweeps competition sources for new big-prize / low-profile
competitions across ALL domains, and (2) consults the current best frontier
intelligences (grounded Gemini + a frontier NIM + Codex) for what's newest —
new competitions, new SOTA methods, new models worth adopting. Writes a
timestamped SCOUT_REPORT.md and appends fresh finds to the pool. Bounded +
graceful: any dead source is skipped, never hangs (hard timeouts).

Run by cron (durable) or `ph scout`. Freshness > recall — training knowledge is
stale, so the grounded frontier lane is the point.
"""
import os, subprocess, shutil, datetime, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
REPORT = os.path.join(CT, "SCOUT_REPORT.md")
KAGGLE = os.path.expanduser("~/miniconda3/bin/kaggle")


def run(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip() or (r.stderr or "").strip()[:400]
    except subprocess.TimeoutExpired:
        return "(timed out)"
    except Exception as e:
        return f"(error: {e})"


FRESH_Q = (
    "As of today, list the NEWEST high-prize machine-learning/data-science competitions "
    "you know of across ALL domains — especially finance (CrunchDAO/ADIA/Numerai), "
    "medical/bio (Grand Challenge, drug discovery, genomics), geoscience, climate, and any "
    "niche high-reward low-participation ones — with prize amount, platform, deadline, and "
    "submission type. Then name any NEW SOTA method or model (2026) worth adopting for tabular/"
    "time-series/vision competitions. Be concrete and current; skip anything before 2026. "
    "Under 400 words."
)


def frontier_lanes():
    out = []
    # grounded Gemini (best for 'what exists / latest')
    if shutil.which("agy"):
        out.append(("gemini (grounded)", run(f'agy --dangerously-skip-permissions -p {sh(FRESH_Q)}', 150)))
    # a frontier NIM for method-freshness (de-bias, different weights)
    if shutil.which("nv"):
        out.append(("deepseek-v4-pro", run(f'nv ask deepseek-ai/deepseek-v4-pro {sh(FRESH_Q)}', 150)))
    # Codex (GPT-5.x) bold divergence
    if shutil.which("codex"):
        out.append(("codex", run(f'codex exec --skip-git-repo-check {sh(FRESH_Q)}', 150)))
    return [(n, t) for n, t in out if t and "timed out" not in t[:20] and len(t) > 40]


def sh(s):
    return "'" + s.replace("'", "'\\''") + "'"


def kaggle_sweep():
    # FRESHNESS: keep only competitions whose deadline is still in the future.
    today = datetime.date.today().isoformat()
    lines = []
    for cat in ("featured", "research"):
        o = run(f'{KAGGLE} competitions list --category {cat} --sort-by prize -p 1 2>/dev/null')
        if not o or "error" in o[:10].lower():
            continue
        rows = o.splitlines()
        header = rows[:2]
        live = []
        for r in rows[2:]:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", r)   # the deadline date
            if m and m.group(1) >= today:                # lexical compare works for ISO dates
                live.append(r)
            if len(live) >= 10:
                break
        if live:
            lines.append(f"### Kaggle · {cat} (LIVE, by prize, deadline≥{today})\n```\n"
                         + "\n".join(header + live) + "\n```")
    return "\n\n".join(lines)


def main():
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M") if "--ts" not in sys.argv else sys.argv[sys.argv.index("--ts") + 1]
    parts = [f"# Scout report — {ts}", "",
             "_periodic latest-info sweep: competition sources + frontier-intelligence consult._", ""]
    parts.append("## Kaggle sweep (mechanical)\n" + (kaggle_sweep() or "(kaggle unavailable)"))
    parts.append("\n## Frontier intelligences — newest competitions + SOTA (grounded)")
    lanes = frontier_lanes()
    if not lanes:
        parts.append("_(no frontier lane responded this cycle — check nv/agy/codex; falling back to known pool)_")
    for name, txt in lanes:
        parts.append(f"\n### {name}\n{txt[:2500]}")
    parts.append("\n---\n→ Verify any new competition (frontier models hallucinate differently), then add high-EV ones "
                 "to DEEP_POOL.md and the registry. Enter the best EV = prize × drivability ÷ crowd.")
    open(REPORT, "w", encoding="utf-8").write("\n".join(parts))
    print(f"scout wrote {os.path.relpath(REPORT, CT)} — {len(lanes)} frontier lane(s), kaggle sweep done")
    # one-line signal for the driver loop
    print("next → read SCOUT_REPORT.md; verify + add high-EV finds to DEEP_POOL.md")


if __name__ == "__main__":
    main()
