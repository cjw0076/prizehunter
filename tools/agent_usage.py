#!/usr/bin/env python3
"""Report Prizehunter agent usage against an adjustable routing policy."""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
POLICY = CONTROL / "AGENT_USAGE_POLICY.tsv"
RECEIPTS = CONTROL / "receipts"
DISPATCH_LOG = CONTROL / "capabilities" / "dispatch_log"
OUT = CONTROL / "AGENT_USAGE_REPORT.md"


@dataclass
class PolicyRow:
    agent: str
    target: float
    max_share: float
    cost_tier: str
    role: str
    route_to: str
    route_away: str


def read_policy(path: Path = POLICY) -> dict[str, PolicyRow]:
    rows: dict[str, PolicyRow] = {}
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t")
        for r in reader:
            if not r.get("agent"):
                continue
            rows[r["agent"]] = PolicyRow(
                agent=r["agent"],
                target=float(r.get("target_share") or 0),
                max_share=float(r.get("max_share") or 1),
                cost_tier=r.get("cost_tier", ""),
                role=r.get("default_role", ""),
                route_to=r.get("route_to", ""),
                route_away=r.get("route_away", ""),
            )
    return rows


def route_counts() -> Counter[str]:
    counts: Counter[str] = Counter()
    # Dispatch receipts are durable and more stable than terminal transcripts.
    for p in RECEIPTS.glob("*.md"):
        text = p.read_text(errors="ignore").lower()
        m = re.search(r"dispatch-[a-z0-9_-]+-to-([a-z0-9_-]+)-\d{8}t", p.name.lower())
        if m:
            target = m.group(1).split("-")[0]
            counts[target] += 1
            continue
        m = re.search(r"cross-agent dispatch:\s*[a-z0-9_-]+\s*->\s*([a-z0-9_-]+)", text)
        if m:
            target = m.group(1).split()[0].split("-")[0]
            counts[target] += 1
    # Count any raw dispatch logs not yet receipt-captured.
    for p in DISPATCH_LOG.glob("*.md"):
        m = re.search(r"_([a-z0-9_-]+)-to-([a-z0-9_-]+)\.md$", p.name.lower())
        if m:
            counts[m.group(2).split("-")[0]] += 1
    return counts


def shares(counts: Counter[str], policy: dict[str, PolicyRow]) -> dict[str, float]:
    agents = sorted(set(policy) | set(counts))
    total = sum(counts[a] for a in agents)
    if total <= 0:
        return {a: 0.0 for a in agents}
    return {a: counts[a] / total for a in agents}


def render(policy: dict[str, PolicyRow], counts: Counter[str]) -> str:
    actual = shares(counts, policy)
    agents = sorted(set(policy) | set(counts))
    lines = [
        "# Agent Usage Report",
        "",
        "This is an operating-control view for Prizehunter. It is based on dispatch receipts/logs, so it measures delegated CLI work, not every thought or local edit.",
        "",
        "| agent | target | actual | max | dispatches | cost | role | action |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for a in agents:
        row = policy.get(a)
        target = row.target if row else 0.0
        max_share = row.max_share if row else 1.0
        act = actual.get(a, 0.0)
        if row and act > max_share:
            action = "throttle unless uniquely fit"
        elif row and act < max(0.0, target * 0.5):
            action = "route more suitable work here"
        elif row:
            action = "within band"
        else:
            action = "unmanaged; add policy row if recurring"
        lines.append(
            f"| {a} | {target:.0%} | {act:.0%} | {max_share:.0%} | {counts[a]} | "
            f"{row.cost_tier if row else ''} | {row.role if row else ''} | {action} |"
        )
    lines += [
        "",
        "## Operating Rule",
        "",
        "- Default route by fit first, then target share.",
        "- High-cost agents should do high-leverage work: strategy, build, verification, final packaging.",
        "- Gemini/local/Hermes sidecars should absorb breadth, critique, extraction, and provider-diversity tasks.",
        "- If one agent exceeds `max_share`, keep using it only for uniquely fitted or urgent founder-gate work.",
        "",
        "## Current Interpretation",
        "",
    ]
    if not counts:
        lines.append("- No dispatch usage recorded yet.")
    else:
        over = [
            a for a, row in policy.items()
            if actual.get(a, 0.0) > row.max_share
        ]
        under = [
            a for a, row in policy.items()
            if actual.get(a, 0.0) < max(0.0, row.target * 0.5)
        ]
        if over:
            lines.append(f"- Over-band: {', '.join(over)}.")
        if under:
            lines.append(f"- Under-used: {', '.join(under)}.")
        if not over and not under:
            lines.append("- Dispatch mix is inside the configured operating band.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=str(POLICY))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    policy = read_policy(Path(args.policy))
    counts = route_counts()
    report = render(policy, counts)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
