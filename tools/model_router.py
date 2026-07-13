#!/usr/bin/env python3
"""Cheap first-pass router for Prizehunter tasks.

This intentionally uses simple rules so routing itself does not spend model
tokens. It produces a compact handoff packet shape before costly dispatch.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
OUT = CONTROL / "MODEL_ROUTING_DECISION.md"


LADDERS = {
    "L0": ("deterministic", "shell/Python/files", "Use local commands before any model call."),
    "L1": ("cheap extraction", "local/Hermes cheap model", "Summarize or structure bounded text; no final claims."),
    "L2": ("sidecar breadth", "Gemini/Hermes", "Get divergence, web-grounded scouting, or assumption attack."),
    "L3": ("high-leverage", "Claude or Codex", "Build, debug, synthesize, or close a concrete artifact."),
    "L4": ("dual review", "Claude + Codex (+ Gemini challenge)", "Pre-submit or ceiling-critical review only."),
}


def choose(task: str, stage: str, risk: str) -> tuple[str, str]:
    t = task.lower()
    s = stage.lower()
    r = risk.lower()
    if r in {"submit", "irreversible", "high"} or re.search(r"submit|final|pre[- ]?submit|leaderboard|ceiling|founder", t):
        return "L4", "Prize-critical or irreversible; use compact packet then dual review."
    if re.search(r"implement|build|debug|fix|package|deck|prototype|writeup|closeout", t):
        return "L3", "Concrete artifact work; use high-leverage builder after compression."
    if re.search(r"idea|brainstorm|scout|web|research|challenge|critique|cross[- ]?domain|alternative", t):
        return "L2", "Breadth or outside-view task; avoid high-cost convergence."
    if re.search(r"extract|summarize|classify|label|parse|table|rules", t):
        return "L1", "Bounded extraction; use cheap lane first."
    if s in {"status", "audit", "check", "receipt"} or re.search(r"status|grep|find|json|csv|count|dashboard|receipt", t):
        return "L0", "Deterministic status or file operation."
    return "L2", "Ambiguous open-ended task; start with sidecar breadth before high-cost build."


def render(task: str, stage: str, risk: str) -> str:
    lane, why = choose(task, stage, risk)
    name, executor, rule = LADDERS[lane]
    return f"""# Model Routing Decision

- task: {task}
- stage: {stage}
- risk: {risk}
- lane: {lane} — {name}
- executor: {executor}
- reason: {why}
- token rule: {rule}

## Compact Packet Template

Use this before dispatching L3/L4:

```text
objective:
evidence/files:
current best metric/state:
blocker/decision:
stop condition:
do not redo:
```

## Next Command

```bash
ph agents
ph dispatch <agent> "<compact packet>"
```
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="*", help="task text to route")
    ap.add_argument("--stage", default="unknown")
    ap.add_argument("--risk", default="normal", choices=["low", "normal", "high", "submit", "irreversible"])
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    task = " ".join(args.task).strip() or "unspecified prizehunter task"
    report = render(task, args.stage, args.risk)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
