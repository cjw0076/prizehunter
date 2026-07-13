#!/usr/bin/env python3
"""Strict judge scoreboard for prizehunter.

This is intentionally skeptical. It is not a cheerleading dashboard. It answers:

- how complete is the entry?
- how well does it satisfy likely judging criteria?
- what is the estimated chance of first place / prize-winning outcome?
- what would a harsh judge punish?
- what is the single next action to raise win probability?
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
POOL = CONTROL / "NEXT_COMPETITION_POOL.tsv"
REGISTRY = CONTROL / "portfolio_registry.tsv"
QUEUE = CONTROL / "PRIZE_WORK_QUEUE_20260613.tsv"
OUT = CONTROL / "PRIZE_JUDGE_SCOREBOARD.md"
OUT_TSV = CONTROL / "PRIZE_JUDGE_SCOREBOARD.tsv"


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader((line for line in f if line.strip() and not line.startswith("#")), delimiter="\t"))


def pct_int(value: str, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def classify_kind(row: dict[str, str]) -> str:
    kind = row.get("kind") or ""
    name = row.get("name") or row.get("competition") or ""
    blob = f"{kind} {name}".lower()
    if any(x in blob for x in ["hackathon", "해커톤", "devpost", "agent", "app"]):
        return "hackathon"
    if any(x in blob for x in ["kaggle", "dacon", "leaderboard", "accuracy", "logloss", "nmae", "ml"]):
        return "leaderboard"
    if any(x in blob for x in ["media", "video", "film", "영상", "디자인", "웹툰", "art", "창작", "예술"]):
        return "creative"
    if any(x in blob for x in ["text", "문학", "독후감", "poetry", "story", "fiction"]):
        return "literature"
    if any(x in blob for x in ["idea", "건축", "창업", "public-data", "공공데이터", "invention"]):
        return "idea"
    return "build"


def campaign_paths(key: str) -> dict[str, bool]:
    base = CONTROL / "campaigns" / key
    return {
        "folder": base.exists(),
        "plan": (base / "PLAN.md").exists(),
        "gap": (base / "PRIZE_GAP_LOOP.md").exists(),
        "collab": (base / "COLLAB_WORKLOOP.md").exists(),
        "creative": (base / "CREATIVE_DIRECTOR_BRIEF.md").exists(),
        "worklog": (base / "AGENT_WORKLOG.md").exists() or (base / "WORKLOG.md").exists(),
    }


def criteria_scores(row: dict[str, str], status: str, progress: int, kind: str, paths: dict[str, bool]) -> dict[str, int]:
    base = min(progress, 100)
    if status == "submitted":
        base = max(base, 82)
    if status in {"ceiling", "drop"}:
        base = min(base, 55)
    if status == "ready-gate":
        base = max(base, 76)
    if status in {"scaffold", "recon"}:
        base = min(max(base, 15 if paths["plan"] else 8), 45)

    official_fit = base + (8 if paths["gap"] else -8)
    evidence = base + (8 if paths["plan"] else -10) + (5 if paths["worklog"] else -5)
    execution = base
    presentation = base
    differentiation = base

    if kind == "leaderboard":
        execution += 8 if "beats" in row.get("blocker", "").lower() or row.get("best", "-") not in {"-", ""} else -8
        presentation -= 10
        differentiation += 4
    elif kind == "hackathon":
        execution += 5 if status == "submitted" else -5
        presentation += 5 if status == "submitted" else -3
    elif kind in {"creative", "literature", "idea"}:
        presentation += 10 if paths["creative"] else -12
        differentiation += 10 if paths["creative"] else -12
        execution += 4 if paths["plan"] else -8

    return {
        "official_fit": clamp(official_fit),
        "execution": clamp(execution),
        "evidence": clamp(evidence),
        "presentation": clamp(presentation),
        "differentiation": clamp(differentiation),
    }


def clamp(v: int) -> int:
    return max(0, min(100, int(v)))


def win_probability(row: dict[str, str], status: str, progress: int, kind: str, scores: dict[str, int]) -> int:
    avg = sum(scores.values()) / len(scores)
    prob = avg * 0.42
    if status == "submitted":
        prob += 8
    if status == "ready-gate":
        prob += 10
    if status in {"ceiling", "drop"}:
        prob -= 25
    if status in {"scaffold", "recon"}:
        prob -= 20
    if "long-shot" in (row.get("blocker", "") + row.get("note", "")).lower():
        prob -= 20
    if "eligibility" in (row.get("blocker", "") + row.get("note", "")).lower() or "founder" in row.get("blocker", "").lower():
        prob -= 8
    if kind == "leaderboard" and row.get("rank1") not in {"-", "", None} and row.get("best") not in {"-", "", None}:
        prob += 6
    return clamp(round(prob))


def harsh_critique(row: dict[str, str], status: str, kind: str, scores: dict[str, int]) -> str:
    text = row.get("blocker") or row.get("note") or ""
    if status == "submitted":
        weak = min(scores, key=scores.get)
        return f"Submitted, but a judge will punish weak {weak.replace('_', ' ')} if evidence is not obvious."
    if status == "ready-gate":
        return "Locally strong, but unsubmitted evidence is worth zero until the founder gate is cleared."
    if status == "ceiling":
        return "Do not pretend effort equals upside; current signal says ceiling unless a genuinely new lever appears."
    if "eligibility" in text.lower():
        return "Eligibility may kill the campaign before quality matters."
    if kind == "leaderboard":
        return "No first-place claim until honest CV, public/private risk, and submit-economy ledger exist."
    if kind in {"creative", "literature"}:
        return "Generic taste loses; Codex must identify the missing-but-judge-aligned angle before production."
    if kind == "idea":
        return "Idea-only is insufficient; needs prototype, adoption path, budget, and measurable impact."
    return "Still too early; rules, rubric, and proof artifact are not locked."


def next_guidance(row: dict[str, str], status: str, kind: str, key: str) -> str:
    if status == "submitted":
        return "Monitor results/notifications; edit only if a clear missing-evidence issue is found before deadline."
    if status == "ready-gate":
        return row.get("next_lever") or "Clear founder gate or park."
    if status == "ceiling":
        return row.get("next_lever") or "Monitor only."
    if kind == "leaderboard":
        return f"Run or update `{CONTROL / 'campaigns' / key / 'PRIZE_GAP_LOOP.md'}`; build baseline/CV/submit ledger."
    if kind in {"creative", "literature", "idea"}:
        return f"Codex fills `{CONTROL / 'campaigns' / key / 'CREATIVE_DIRECTOR_BRIEF.md'}` before Claude build."
    if kind == "hackathon":
        return "Verify eligibility/deadline, then build smallest hosted demo with repo/video/deck."
    return row.get("next_lever") or "Recon official rules and decide GO/NO-GO."


def registry_rows() -> list[dict[str, str]]:
    return read_tsv(REGISTRY)


def pool_rows() -> list[dict[str, str]]:
    rows = []
    for r in read_tsv(POOL):
        rows.append(
            {
                "key": r.get("id", ""),
                "name": r.get("name", ""),
                "status": r.get("status", "pool"),
                "progress": "5",
                "best": "-",
                "rank1": "-",
                "blocker": r.get("note", ""),
                "next_lever": "",
                "kind": r.get("kind", ""),
                "priority": r.get("priority", ""),
                "prize_krw": r.get("prize_krw", ""),
                "source": r.get("source", ""),
                "url": r.get("url", ""),
            }
        )
    return rows


def merge_rows() -> list[dict[str, str]]:
    by_key = {r["key"]: r for r in pool_rows() if r.get("key")}
    for r in registry_rows():
        key = r.get("key", "")
        if not key:
            continue
        merged = {**by_key.get(key, {}), **r}
        merged.setdefault("name", key)
        merged.setdefault("priority", "ACTIVE")
        by_key[key] = merged
    rows = list(by_key.values())
    def sort_key(r: dict[str, str]) -> tuple[int, int, str]:
        status = r.get("status", "")
        prio = r.get("priority", "")
        score = pct_int(r.get("score", "0"))
        active_bonus = 1000 if status in {"ready-gate", "active"} else 900 if status in {"submitted"} else 700 if prio == "P0" else 500 if prio == "P1" else 0
        return (active_bonus, score, r.get("key", ""))
    return sorted(rows, key=sort_key, reverse=True)


def make_scoreboard() -> None:
    rows_out = []
    for r in merge_rows():
        key = r.get("key", "")
        if not key or key == "key":
            continue
        status = r.get("status", "pool")
        progress = pct_int(r.get("progress", "5"), 5)
        kind = classify_kind(r)
        paths = campaign_paths(key)
        scores = criteria_scores(r, status, progress, kind, paths)
        prob = win_probability(r, status, progress, kind, scores)
        completeness = round(sum(scores.values()) / len(scores))
        rows_out.append(
            {
                "key": key,
                "name": r.get("name") or key,
                "priority": r.get("priority") or "ACTIVE",
                "lane": kind,
                "status": status,
                "progress": str(progress),
                "completeness": str(completeness),
                "win_prob": str(prob),
                "official_fit": str(scores["official_fit"]),
                "execution": str(scores["execution"]),
                "evidence": str(scores["evidence"]),
                "presentation": str(scores["presentation"]),
                "differentiation": str(scores["differentiation"]),
                "harsh_critique": harsh_critique(r, status, kind, scores),
                "next_guidance": next_guidance(r, status, kind, key),
            }
        )
    rows_out.sort(key=lambda r: (int(r["win_prob"]), int(r["completeness"])), reverse=True)

    cols = [
        "key",
        "name",
        "priority",
        "lane",
        "status",
        "progress",
        "completeness",
        "win_prob",
        "official_fit",
        "execution",
        "evidence",
        "presentation",
        "differentiation",
        "harsh_critique",
        "next_guidance",
    ]
    with OUT_TSV.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows_out:
            f.write("\t".join(str(r[c]).replace("\n", " ") for c in cols) + "\n")

    with OUT.open("w", encoding="utf-8") as f:
        f.write("# Prize Judge Scoreboard\n\n")
        f.write(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}\n")
        f.write("- stance: strict evaluator, not project advocate\n")
        f.write("- win_prob: heuristic first-place/prize-winning probability, capped by evidence and gates\n\n")
        f.write("## Rubric\n\n")
        f.write("| Field | Meaning |\n|---|---|\n")
        f.write("| official_fit | rules, rubric, eligibility, theme fit |\n")
        f.write("| execution | code/model/prototype/manuscript/media feasibility and polish |\n")
        f.write("| evidence | sources, tests, demos, provenance, revision logs, receipts |\n")
        f.write("| presentation | visual/story/deck/video/readability/first-glance strength |\n")
        f.write("| differentiation | why this beats generic 100% submissions |\n\n")
        f.write("## Top Watchlist\n\n")
        f.write("| win% | complete | lane | status | key | competition | harsh critique | next |\n")
        f.write("|---:|---:|---|---|---|---|---|---|\n")
        for r in rows_out[:35]:
            f.write(
                f"| {r['win_prob']} | {r['completeness']} | {r['lane']} | {r['status']} | `{r['key']}` | {r['name']} | {r['harsh_critique']} | {r['next_guidance']} |\n"
            )
        f.write("\n## How Codex Uses This\n\n")
        f.write("1. Every prizehunter cycle, regenerate with `ph judge`.\n")
        f.write("2. If win probability is low because evidence/presentation/differentiation is weak, Codex writes the exact deficiency into the campaign brief.\n")
        f.write("3. If a leaderboard ceiling is claimed, Codex must ask a side agent or alternate method to refute it before parking.\n")
        f.write("4. For creative contests, Codex blocks Claude build until `CREATIVE_DIRECTOR_BRIEF.md` names the missing-but-judge-aligned angle.\n")
        f.write("5. For submitted contests, only edit when the scorecard identifies a concrete missing-evidence issue before deadline.\n")

    print(OUT)
    print(OUT_TSV)
    print(f"rows={len(rows_out)}")


if __name__ == "__main__":
    make_scoreboard()
