#!/usr/bin/env python3
"""Prizehunter novelty/value-proposition board.

Prize money is evidence that ordinary baselines are not enough. This board
forces every active chase to state the non-obvious value proposition, proof
route, and stale-approach risk before spending more cycles.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
QUALITY = CONTROL / "QUALITY_GATE_REPORT.tsv"
OUT_MD = CONTROL / "NOVELTY_VALUE_BOARD.md"
OUT_TSV = CONTROL / "NOVELTY_VALUE_BOARD.tsv"

ACTIVE_STATUSES = {"active", "submitted", "ceiling", "ready-gate", "blocked", "recon", "scaffold"}

LEADERBOARD_KEYS = {
    "236722",
    "236690",
    "kdd-unirec-2026",
    "adia-structural-break-rt",
    "arc-whitebox-2026",
    "neurogolf-2026",
    "crunchdao-obesity-3",
    "numerai-main",
    "zindi-worldcup-2026",
    "nexon-nypc-2026",
    "arc-prize-2026",
    "orbit-wars",
    "236730",
    "236727",
}

LANE_OVERRIDES = {
    "arc-whitebox-2026": "leaderboard",
    "arc-prize-2026": "leaderboard",
    "numerai-main": "leaderboard",
    "nexon-nypc-2026": "leaderboard",
    "datacontest-motie": "publicdata_product",
    "gitlab-transcend-2026": "hackathon",
    "aic-culture-data": "publicdata_product",
    "aic-usecase": "hackathon",
    "2026-create-the-future": "idea_design",
}

NOVELTY_OVERRIDES = {
    "arc-whitebox-2026": {
        "thesis": "Beat tutorial covariance/MC by deriving a stronger ReLU covariance estimator, not by spending more samples.",
        "proof": "Mini/full split improvement over 1.7494e-06, residual family report, subprocess validation, then gated AIcrowd submit.",
        "risk": "fixed covariance+MC blend is now leaderboard-middle and visually indistinguishable from common baseline tuning",
        "next": "Implement or test exact/bivariate ReLU covariance and antithetic variance-reduction probes.",
    },
    "arc-prize-2026": {
        "thesis": "Turn public game internals into per-game solvers and reusable action-effect memory, not blind ARC-AGI prompting.",
        "proof": "At least one public game solved locally with replay/trace and generalized action-effect notes before upload.",
        "risk": "random/deterministic sweeps and generic LLM planning are already exhausted and score 0.0",
        "next": "Solve ft09 with a public-state oracle/constraint reducer, then generalize to r11l/tr87 planners.",
    },
    "numerai-main": {
        "thesis": "Find a stable orthogonal signal family under era/exposure checks, not another public example-pred blend.",
        "proof": "Feature-family or model-class variation improves mean without severe sharpe/exposure degradation; no-stake validation only.",
        "risk": "small+wisdom rank ensembles are incremental and likely not prize-distinct",
        "next": "Run one compact family/model-class confirmation and keep upload gated until robustness improves.",
    },
    "nexon-nypc-2026": {
        "thesis": "Build a reusable private arena/opponent suite that converts hidden agent behavior into policy search assets.",
        "proof": "Official runner adapter plus opponent suite scorecard after founder provides Arena/practice assets.",
        "risk": "toy arena alone is preparation, not a contest advantage",
        "next": "After access, replace toy runner with official adapter and rerun deterministic scorecard.",
    },
    "datacontest-motie": {
        "thesis": "Sell an operator-validated energy support decision system, not a public-data dashboard.",
        "proof": "Real founder/operator walkthrough row, freshness check, impact math tied to actual support-program action.",
        "risk": "thin dashboard/reskin will look like every public-data contest entry",
        "next": "Run one real walkthrough and record objections/changes with the existing recorder.",
    },
    "gitlab-transcend-2026": {
        "thesis": "Use live Orbit graph context as a merge guardrail and AI Catalog asset, not a generic MR summarizer.",
        "proof": "glab Orbit live receipt, schema/query output, AI Catalog URL, failing/passing guardrail demo.",
        "risk": "offline mock data reads as a demo scaffold and loses theme eligibility",
        "next": "Unlock live Orbit/glab auth or park rather than polishing sample JSON.",
    },
    "orbit-wars": {
        "thesis": "Only revive with a live-transfer simulator/opponent generator, not another heuristic tweak.",
        "proof": "Local proxy predicts live score movement across archived bots before spending a Kaggle submit.",
        "risk": "garrison gates overfit; v12 already failed live transfer",
        "next": "Park unless broader proxy/MCTS-like opponent generator is built.",
    },
    "aic-culture-data": {
        "thesis": "HanMoon must be a distinct cross-track cultural-data product with written eligibility clearance.",
        "proof": "Organizer confirms dual-work submission is allowed; then evidence-backed demo/video can proceed.",
        "risk": "duplicate-entry ambiguity can disqualify even a strong product",
        "next": "Obtain written organizer confirmation before any external submission polish.",
    },
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    if not lines:
        return []
    return list(csv.DictReader(lines, delimiter="\t"))


def lane_for(row: dict[str, str], qrow: dict[str, str] | None) -> str:
    key = row.get("key", "")
    if key in LANE_OVERRIDES:
        return LANE_OVERRIDES[key]
    if key in LEADERBOARD_KEYS or row.get("direction") in {"min", "max"}:
        return "leaderboard"
    if qrow and qrow.get("lane"):
        return qrow["lane"]
    blob = " ".join(row.get(k, "") for k in ("key", "metric", "blocker", "next_lever")).lower()
    if re.search(r"devpost|hackathon|agent|software|sw", blob):
        return "hackathon"
    if re.search(r"공공데이터|public.?data|data\.go\.kr", blob):
        return "publicdata_product"
    if re.search(r"영상|film|design|creative|art|웹툰", blob):
        return "creative_media"
    if re.search(r"idea|future|기획|제안", blob):
        return "idea_design"
    return "other"


def default_novelty(row: dict[str, str], lane: str) -> dict[str, str]:
    if lane == "leaderboard":
        return {
            "thesis": "Find a new generalizing signal or simulator, not public leaderboard/luck tuning.",
            "proof": "Honest CV or local-public/private transfer proof plus one ablation that beats current best.",
            "risk": "baseline ensembles and public-response tuning become stale quickly in prize pools",
            "next": row.get("next_lever", "") or "Define the non-obvious signal and its falsification test.",
        }
    if lane == "publicdata_product":
        return {
            "thesis": "Create an operational decision product with real adoption evidence, not a dashboard.",
            "proof": "Data provenance, real-user walkthrough, impact math, and a concrete action taken from the tool.",
            "risk": "public-data dashboards are common and usually judged as low originality",
            "next": row.get("next_lever", "") or "Record real operator validation and one product-changing objection.",
        }
    if lane == "hackathon":
        return {
            "thesis": "Expose a sponsor-native workflow that could be adopted tomorrow, not a generic agent wrapper.",
            "proof": "Hosted/live integration evidence, repo/license, short demo, and sponsor-rubric mapping.",
            "risk": "generic chat/copilot demos are saturated",
            "next": row.get("next_lever", "") or "Identify the sponsor-specific workflow hook and prove it live.",
        }
    if lane == "creative_media":
        return {
            "thesis": "Lead with a first-glance concept hook and rights-safe production system.",
            "proof": "Final media, variants, visual critique, and AI/rights compliance.",
            "risk": "generic AI visuals are visually stale and easy to reject",
            "next": row.get("next_lever", "") or "Generate distinct routes and select one with critique evidence.",
        }
    if lane == "idea_design":
        return {
            "thesis": "Make the proposal implementable with a buyer/operator, cost model, and measurable impact.",
            "proof": "Diagram/mockup, stakeholder map, cost/adoption plan, and risk register.",
            "risk": "slogan-level ideas rarely beat buildable concepts",
            "next": row.get("next_lever", "") or "Add operator/buyer proof and measurable impact.",
        }
    return {
        "thesis": "Do not continue until the distinct value proposition is explicit.",
        "proof": "Official rules plus a novelty proof unique to this contest.",
        "risk": "unclear lane means high chance of generic work",
        "next": row.get("next_lever", "") or "Run recon and write the novelty thesis.",
    }


def stale_score(row: dict[str, str], novelty: dict[str, str]) -> int:
    text = " ".join([row.get("blocker", ""), row.get("next_lever", ""), *novelty.values()]).lower()
    score = 0
    for pat in (r"baseline", r"generic", r"dashboard", r"wrapper", r"monitor only", r"accepted", r"submitted"):
        if re.search(pat, text):
            score += 1
    if row.get("status") == "submitted" and row.get("direction") in {"min", "max"}:
        score += 2
    if row.get("status") == "ceiling":
        score += 2
    return min(score, 5)


def rows_for_board() -> list[dict[str, str]]:
    quality = {row["key"]: row for row in read_tsv(QUALITY) if row.get("key")}
    out = []
    for row in read_tsv(REGISTRY):
        key = row.get("key", "")
        status = row.get("status", "")
        if not key or status == "drop" or status not in ACTIVE_STATUSES:
            continue
        qrow = quality.get(key)
        lane = lane_for(row, qrow)
        novelty = NOVELTY_OVERRIDES.get(key, default_novelty(row, lane))
        out.append(
            {
                "key": key,
                "lane": lane,
                "status": status,
                "progress": row.get("progress", ""),
                "win_probability": qrow.get("win_probability", "-") if qrow else "-",
                "stale_risk": str(stale_score(row, novelty)),
                "value_thesis": novelty["thesis"],
                "proof": novelty["proof"],
                "risk": novelty["risk"],
                "next": novelty["next"],
            }
        )
    out.sort(key=lambda r: (-(int(r["stale_risk"] or 0)), -(int(r["progress"] or 0))))
    return out


def render_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Prizehunter Novelty Value Board",
        "",
        "Auxiliary goal: prize money means common methods are insufficient. Every active campaign must carry a fresh value proposition, a proof route, and a stale-approach kill rule.",
        "",
        "| stale risk | key | lane | status | progress | win% | new value thesis | proof route | next novelty action |",
        "|---:|---|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {stale_risk} | `{key}` | {lane} | {status} | {progress} | {win_probability} | {value_thesis} | {proof} | {next} |".format(
                **{k: (v or "-").replace("|", "/") for k, v in row.items()}
            )
        )
    lines += [
        "",
        "## Operating Rules",
        "",
        "- A higher stale risk means the current approach can look ordinary to judges or leaderboard competitors.",
        "- Do not spend long cycles on baseline tuning unless the proof route explains why it is non-obvious.",
        "- For judged contests, novelty must be visible in the first minute of review.",
        "- For leaderboard contests, novelty must be falsifiable through transfer, residual, or ablation evidence.",
        "- Submitted/accepted is not the terminal state unless the value proposition has either won or hit a documented kill rule.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = rows_for_board()
    OUT_MD.write_text(render_md(rows), encoding="utf-8")
    with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["key", "lane", "status", "progress", "win_probability", "stale_risk", "value_thesis", "proof", "risk", "next"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(OUT_MD)
    print(OUT_TSV)
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
