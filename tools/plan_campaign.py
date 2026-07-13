#!/usr/bin/env python3
"""plan_campaign.py — decompose one competition into a one-touch-to-#1 plan.

Given a competition (key + name + signals), produce campaigns/<key>/PLAN.{md,json}:
  final objective  ->  phases (예선/본선, 1차/2차, ...)  ->  sub-objectives
  + required deliverables auto-detected (submission / code repo / demo video /
    presentation slides+script / paper / writeup) from the competition type.
The executor (run_campaign.sh) walks this plan, dispatching each sub-objective.

Usage:
  plan_campaign.py --key <your-key> --name "..." [--domain ml] [--metric accuracy]
                   [--platform dacon] [--prize 10000]
"""
import json, re, sys, os, argparse

# methodology sub-objectives that move a leaderboard comp toward #1 (METHODOLOGY phases)
LB_SUBOBJ = [
    ("judge-intent-gap", "mine hidden organizer intent, likely private-score traps, our current deficiencies, and 120% backlog", "codex"),
    ("recon", "extract metric, split %, daily limit, award structure, external-data policy", "claude"),
    ("data-semantics", "understand what each column/target means; find the rank-1 lever", "claude"),
    ("honest-cv", "build a leak-free CV harness calibrated to a public anchor", "codex"),
    ("leak-detection", "check every candidate feature/OOF for leakage before trusting it", "claude"),
    ("baseline-build", "implement a clean baseline pipeline + first submission", "codex"),
    ("signal-ceiling", "find the honest ceiling; adversarially triangulate with another vendor", "claude"),
    ("optimize", "push toward rank-1 within honest signal; calibrate; manage submission economy", "codex"),
]

INTERACTIVE_AGENT_SUBOBJ = [
    ("official-harness", "reproduce the official local/API harness, rules, score function, action limits, and submission path", "codex"),
    ("environment-taxonomy", "cluster public environments by observation space, action grammar, object dynamics, hidden goal type, and failure mode", "claude"),
    ("cheap-baseline", "run a deterministic low-cost baseline and record public-game score, cost, latency, and traces", "codex"),
    ("trace-memory", "persist game traces, discovered mechanics, failed hypotheses, and reusable skills for retrieval by later agents", "codex"),
    ("world-model-search", "build scripted exploration plus state abstraction, transition inference, search/MCTS/planning, and rollback logic", "claude"),
    ("llm-policy-router", "use frontier/local models only where they add value: hypothesis generation, trace critique, or code synthesis, with a cost cap", "codex"),
    ("adversarial-eval", "have a side agent refute overfit claims using held-out public games, shuffled goals, and cost-normalized comparisons", "gemini"),
    ("milestone-decision", "decide Milestone #1 vs #2 based on measurable public score/cost, not prize headline or wishful extrapolation", "codex"),
]

JUDGED_SUBOBJ = [
    ("judge-intent-gap", "mine organizer taste, hidden judging intent, prior winners, taboo patterns, and our current deficiencies", "codex"),
    ("official-recon", "extract rules, eligibility, AI-use/IP constraints, file formats, deadlines, and submission fields", "claude"),
    ("reference-mining", "collect prior winners, organizer language, visual/literary/business references, and rights-safe assets", "codex"),
    ("route-generation", "generate multiple non-obvious routes and select one with kill criteria", "codex"),
    ("prototype-or-draft", "produce the core artifact: prototype, manuscript, storyboard, visual board, deck, or business package", "claude"),
    ("visual-and-presentation", "Codex visual QA: brand/character/style, screenshots, thumbnail/first-glance impact, deck/video polish", "codex"),
    ("outside-challenge", "dispatch Gemini/side agent to attack originality, feasibility, overclaim, and eligibility risk", "gemini"),
    ("deficiency-closure", "map every P0/P1 gap to a final artifact, source, or explicit kill/park decision", "claude"),
]

def detect_deliverables(name, platform, domain, metric):
    n = (name + " " + platform + " " + domain).lower()
    d = []
    if re.search(r'arc-agi-3|interactive agent|agentic reasoning|turn-based|environment|world.?model', n):
        d += [("official_harness", "local/API harness with reproducible score command and trace capture"),
              ("agent_policy", "agent implementation with exploration, dynamics inference, planning, and fallback routes"),
              ("trace_corpus", "public-game traces, discovered mechanics, failed hypotheses, and cost ledger"),
              ("milestone_report", "score/cost decision memo for Milestone #1 vs #2")]
    if re.search(r'문학|문예|독후감|에세이|글쓰기|소설|시|스토리|시나리오|writing|fiction|poetry|essay', n):
        d += [("manuscript", "final manuscript with contest-specific voice, structure, and format compliance"),
              ("author_dossier", "bio, activity record, portfolio index, statement, and rights/AI-use disclosure"),
              ("revision_log", "macro, flow, and line-edit passes with outside-reader critique")]
    if re.search(r'디자인|영상|미디어|웹툰|캐릭터|창작|아트|예술|사진|포스터|film|video|art|design|webtoon', n):
        d += [("creative_direction", "Codex visual bible: concept, identity, palette, type, references, do/don't list"),
              ("storyboard_or_key_visuals", "storyboard, key frames, thumbnails, or presentation board"),
              ("final_media_package", "final files plus source/provenance/AI-use notes")]
    if re.search(r'아이디어|건축|창업|제안|기획|policy|business|startup|architecture|invention', n):
        d += [("concept_package", "problem framing, stakeholder map, solution, feasibility, adoption path"),
              ("prototype_or_mockup", "clickable prototype, render, dashboard, or proof artifact"),
              ("business_case", "KPI, budget, rollout, risk, and impact appendix")]
    if metric and metric not in ("n/a", "none", "", "judged"):
        d.append(("leaderboard_submission", "best scoring file submitted within daily limit"))
    if re.search(r'hackathon|해커톤|devpost|agent|lablab|mlh', n):
        d += [("code_repo", "public MIT repo, reproducible one-command demo"),
              ("demo_video", "<5min screen+voice demo (storyboard+script auto; recording human)"),
              ("writeup", "Devpost/submission writeup: problem, approach, impact")]
    if re.search(r'논문|paper|academic|학회|journal', n):
        d.append(("paper", "method + honest results + reproducibility appendix"))
    if re.search(r'발표|presentation|pitch|본선|finalist|demo day|시연', n):
        d += [("slides", "presentation deck (markdown content auto; render gated)"),
              ("talk_script", "per-slide speaker script + Q&A prep")]
    if not d:
        d.append(("leaderboard_submission", "best scoring file (default deliverable)"))
    # dedupe preserve order
    seen=set(); out=[]
    for k,v in d:
        if k not in seen: seen.add(k); out.append((k,v))
    return out

def detect_phases(name):
    n = name.lower()
    if re.search(r'본선|예선|qualifier|final', n) or re.search(r'1차|2차|round\s*[12]', n):
        return [("phase1_qualifier", "예선/1차: reach the cut (leaderboard threshold + required artifacts)"),
                ("phase2_final", "본선/2차: win the round (often presentation/live demo + final score)")]
    return [("single", "single-phase: maximize leaderboard rank + required deliverables")]

def registry_campaign_dir(key, here):
    reg = os.path.abspath(os.path.join(here, "..", "portfolio_registry.tsv"))
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    if not os.path.exists(reg):
        return None
    header = None
    with open(reg, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            row = dict(zip(header, parts))
            if row.get("key") == key and row.get("dir"):
                return os.path.join(root, row["dir"])
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--domain", default="ml"); ap.add_argument("--metric", default="accuracy")
    ap.add_argument("--platform", default="dacon"); ap.add_argument("--prize", default="")
    ap.add_argument("--url", default="")
    here = os.path.dirname(__file__)
    ap.add_argument("--out", default=os.path.join(here, "..", "campaigns"))
    a = ap.parse_args()

    phases = detect_phases(a.name)
    delivs = detect_deliverables(a.name, a.platform, a.domain, a.metric)
    judged_like = (
        a.metric in ("judged", "none", "n/a", "")
        or re.search(r"text|media|idea|vision|문학|디자인|영상|아이디어|예술|스토리", a.domain + " " + a.name, re.I)
    )
    interactive_agent = re.search(r'arc-agi-3|interactive agent|agentic reasoning|turn-based|environment|world.?model', a.domain + " " + a.name, re.I)
    subobjs = INTERACTIVE_AGENT_SUBOBJ if interactive_agent else (JUDGED_SUBOBJ if judged_like else LB_SUBOBJ)
    objective_verb = (
        "Reach prize-winning judged quality"
        if judged_like
        else "Reach rank #1"
    )
    if judged_like:
        phases = [
            (
                pid,
                obj.replace(
                    "maximize leaderboard rank + required deliverables",
                    "maximize judge fit, originality, feasibility, presentation, and required deliverables",
                ),
            )
            for pid, obj in phases
        ]
    plan = {
        "key": a.key, "name": a.name, "platform": a.platform, "domain": a.domain,
        "official_url": a.url,
        "metric": a.metric, "prize": a.prize,
        "final_objective": f"{objective_verb} on {a.name} by identifying hidden judge intent, closing our deficiencies, and producing 120%+ evidence beyond the written requirements.",
        "phases": [{"id": pid, "objective": obj,
                    "sub_objectives": [{"id": s, "task": t, "route": r, "status": "todo"}
                                       for s, t, r in subobjs]} for pid, obj in phases],
        "deliverables": [{"id": k, "spec": v, "status": "todo",
                          "auto": k not in ("demo_video",) }  # video recording is human-gated
                         for k, v in delivs],
        "gates": ["external submission founder-gated", "account signup/ToS human",
                  "video recording + live presentation human"],
    }
    d = registry_campaign_dir(a.key, here) or os.path.join(a.out, a.key)
    os.makedirs(d, exist_ok=True)
    json.dump(plan, open(os.path.join(d, "PLAN.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(d, "PLAN.md"), "w") as o:
        o.write(f"# Campaign Plan — {a.name}\n\n")
        o.write(f"- key={a.key} platform={a.platform} domain={a.domain} metric={a.metric} prize={a.prize or 'TBD'}\n")
        if a.url:
            o.write(f"- official_url={a.url}\n")
        o.write(f"\n## Final objective\n{plan['final_objective']}\n")
        o.write("\n## Required pre-build gap loop\nRun `ph gap {key} \"{name}\"` and keep `PRIZE_GAP_LOOP.md` updated as assumptions change.\n".format(key=a.key, name=a.name.replace('"', '\\"')))
        for ph in plan["phases"]:
            o.write(f"\n## Phase: {ph['id']}\n{ph['objective']}\n\n")
            for s in ph["sub_objectives"]:
                o.write(f"- [ ] **{s['id']}** ({s['route']}): {s['task']}\n")
        o.write("\n## Deliverables (auto = agent-producible end-to-end)\n\n")
        for dl in plan["deliverables"]:
            o.write(f"- [ ] **{dl['id']}** {'🤖auto' if dl['auto'] else '🙋human-gated'}: {dl['spec']}\n")
        o.write("\n## Gates\n")
        for g in plan["gates"]: o.write(f"- ⛔ {g}\n")
    print(os.path.join(d, "PLAN.md"))
    print(f"phases={len(plan['phases'])} subobj={len(subobjs)} deliverables={[x['id'] for x in plan['deliverables']]}")

if __name__ == "__main__":
    main()
