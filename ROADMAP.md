# Roadmap — from competition winner to a general goal service

PrizeHunter's thesis: **autonomous competition agents that get smarter with every
challenge.** Competitions are the beachhead because they have what every honest
autonomy claim needs — an *external verifier* (a leaderboard, a judge, prize money).
The long-term product is a general **goal service**: goal in → verified outcome out.

This roadmap is maintained by the agents that run the product. Issues and
milestones on GitHub are the live sprint board; this file is the direction.

## How we develop (agile, agent-run)

- **1-week sprints.** Each sprint ships at least one user-visible improvement.
- **Release gate**: `ph qa` must be green before any push (fresh-clone smoke,
  tool parse, trigger parity, seed files, secret scan).
- **QA team** (`ph qa-team`): once per sprint, a panel of role-specialized reviewers
  (correctness / security / product / honesty), each on a different model, reviews the
  increment; verified findings become issues. See [`RND.md`](RND.md).
- **R&D loop** (`ph rnd`): findings + council + calibration feed an evolutionary
  variation→selection→retention cycle on the system's own methods, scored on the
  north-star metrics. The system improves itself, not just its throughput.
- **Retro**: repeated lessons in `results/LESSONS.md` are treated as system bugs —
  fix the tool, not the reminder.

## Stage 1 — Competition autonomy (now)

The loop that exists today: discover → triage → plan → build → optimize →
submit → settle → learn, with per-competition agent-designed goal loops
(`ph goal --design`), a heterogeneous council (`ph council`), an approach
ontology that compounds across competitions (`ph ontology` / `ph inherit`),
and just-in-time credential elicitation (`ph onboard` / `ph session`).

Sprint focus: **product hardening** — fresh-clone experience, QA harness,
issue self-reporting, measured activation (clone → first registered
competition without human help).

## Stage 2 — Proof of compounding (next)

"It gets smarter every round" must be **measured, not claimed**:

- Calibration: predicted win% vs. actual outcomes (Brier score) trending down.
- Priming lift: first-submission score on a new competition in a known lane,
  higher than historical first submissions in that lane.
- Ontology coverage: share of new competitions that inherit a non-empty,
  fitness-positive strategy from `ph inherit`.
- Endurance: cycles per competition without human intervention.

If these numbers don't move, the compounding story is marketing — and the
sprint goal becomes fixing the learning loop, not the slide deck.

## Stage 3 — Adjacent verified outcomes

Generalize only along the invariant that made competitions work: **an external
verifier exists.** Candidates: grant/hackathon applications, public benchmarks,
bug bounties, certification-style challenges. The test of generality is loop
reuse — how much of discover/triage/goal-design/settle transfers unchanged.

## Stage 4 — The goal service

A user registers a goal **with its verification criterion**; the agent designs
the goal loop (as it already does per competition archetype), drives it to the
verified outcome, and the ontology compounds across *all* goals, not just
competitions. Competitions turn out to be the special case, not the product.

What we deliberately do **not** generalize to (yet): goals without an external
verifier (where the system would grade its own homework), real-money spending,
and legal actions. Human gates (account signup, 2FA/CAPTCHA, final external
submission, spend) stay human — a product that claims otherwise is lying.

## Principles that don't change per stage

1. **Honesty over theater**: losses are recorded as losses; ceilings must
   survive adversarial review before anyone stops pushing.
2. **Agent-agnostic**: PrizeHunter rides inside Claude Code / Codex / Gemini —
   it never locks you into one model host.
3. **Everything on the record**: registry, ledgers, postmortems, ontology —
   durable files, greppable, auditable.
