# Evolutionary development — how PrizeHunter improves *itself*

Two learning loops run in this system, at two levels:

| Loop | Evolves | Cycle | Tool |
|---|---|---|---|
| **Approach ontology** | how we ATTACK competitions | settled outcomes reweight `favors` edges | `ph ontology` / `ph inherit` |
| **R&D loop** | the SYSTEM's own methods (verbs, gates, archetypes, QA) | variation → selection → retention on north-star metrics | `ph rnd` |

Both are the same evolutionary shape — variation, selection by measured fitness,
retention of what survives — applied at different levels. The ontology makes each
*competition* start smarter; the R&D loop makes the *system* get better at running
competitions at all. (This is the HyperAgents-style meta-level: don't just learn
tasks, learn how to do tasks better.)

## The standing QA team (`ph qa-team`)

Mechanical gates (`ph qa`) catch what a script can check. Real defects — the
`prizehunter_ui` module that crashed 7 tools while `py_compile` stayed green — need
a *review*, and a single reviewer misses what a panel catches. So QA is a **team of
role-specialized reviewers, each on a different model**:

- **correctness** — fresh-clone breakage, logic bugs, wrong outputs
- **security** — credential/shell/abuse surface, secret leakage, sandbox gaps
- **product** — onboarding friction, docs that overpromise
- **honesty** — no-launder: claims the code doesn't back (both directions)

Roles are round-robined across the operator's council members, so the review is
heterogeneous — same-weights review is a logic check, not QA. The calling agent
synthesizes, **verifies each finding against the code** (models hallucinate
differently), files confirmed P0/P1 as issues, and hands the systemic ones to R&D.

## The R&D loop (`ph rnd`) — variation → selection → retention

```
  QA findings ─┐
  council      ├─▶ variation (propose/harvest) ─▶ experiment ─▶ result vs baseline
  calibration ─┤                                                      │
  open issues ─┘                                                      ▼
        retained heuristics ◀── retention ◀── selection (beat the north-star metric?)
```

- **variation** — `ph rnd propose` seeds candidate system improvements; `ph rnd
  harvest` turns confirmed QA-team findings into experiments; `ph rnd add` for your own.
- **selection** — each experiment names a target metric (activation / brier / uplift /
  endurance / qa-findings / coverage). `ph rnd result` records baseline→result;
  `ph rnd select` **keeps only those that measurably beat baseline**, drops the rest.
- **retention** — kept experiments are retained system heuristics; dropped ones carry
  a recorded note so the same dead end isn't re-proposed. The ledger
  (`RND_EXPERIMENTS.tsv`) is the system's own evolutionary record.

## Why this is evolution and not a backlog

A backlog is a wishlist. This loop has the three things evolution needs:
1. **Variation** from multiple independent sources (QA, council, calibration, issues).
2. **Selection** by an external fitness signal (the north-star metrics), not by opinion.
3. **Retention** — survivors become the system's defaults; failures leave a scar the
   system reads before re-proposing.

Run it every sprint: `ph qa-team` → verify → `ph rnd harvest` → run the top bet →
`ph rnd result` → `ph rnd select`. Over time the system has fewer failure points and
a growing set of *proven* methods — the same reason the ontology makes competitions
compound, applied to the machine itself.

## Status in this build

Working: `ph qa` (8 gates), `ph qa-team` (heterogeneous panel), `ph rnd` (full
variation→selection→retention cycle, ledger seeded from the first council QA round).
The first retained heuristic (E005) is the runtime-import gate that would have caught
two P0s before they shipped. Deeper automation (auto-running the top experiment,
closing the loop from `ph rnd select` back into a code change) grows with real usage.
