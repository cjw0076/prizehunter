#!/usr/bin/env python3
"""Build a chase board so submitted work keeps moving toward rank-1/winning."""
from __future__ import annotations

import csv
import math
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
QUALITY = CONTROL / "QUALITY_GATE_REPORT.tsv"
OUT = CONTROL / "POST_SUBMISSION_CHASE_BOARD.md"

# Empty in the shipped product: leaderboard lane is inferred per-row from the
# registry (any row with direction "max"/"min" counts as a leaderboard chase —
# see infer_lane). Add your own keys here only to force-classify edge cases.
LEADERBOARD_KEYS: set[str] = set()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    if not lines:
        return []
    return list(csv.DictReader(lines, delimiter="\t"))


def score_gap(row: dict[str, str]) -> str:
    best = row.get("best", "-")
    rank1 = row.get("rank1", "-")
    direction = row.get("direction", "none")
    try:
        b = float(best)
        r = float(rank1)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(b) or not math.isfinite(r):
        return "-"
    if direction == "max":
        return f"{max(0.0, r - b):.6g}"
    if direction == "min":
        return f"{max(0.0, b - r):.6g}"
    return "-"


def infer_lane(row: dict[str, str], qmap: dict[str, dict[str, str]]) -> str:
    key = row.get("key", "")
    if key in LEADERBOARD_KEYS or row.get("direction") in {"max", "min"}:
        return "leaderboard"
    if key in qmap and qmap[key].get("lane"):
        return qmap[key]["lane"]
    return "judged"


def chase_mode(row: dict[str, str], lane: str) -> str:
    status = row.get("status", "")
    if lane == "leaderboard":
        if status == "ceiling":
            return "ceiling_refute_or_park"
        if status in {"submitted", "active", "polishing"}:
            return "rank1_chase"
        if status == "blocked":
            return "unblock_data_or_auth_then_rank1_chase"
        return "scaffold_to_score_loop"
    if status == "submitted":
        return "monitor_award_or_edit_if_material_gap"
    if status in {"active", "polishing", "ready-gate"}:
        return "judge_satisfaction_iteration"
    if status == "blocked":
        return "clear_gate_or_park"
    return "rubric_recon"


def next_action(row: dict[str, str], lane: str, mode: str, qrow: dict[str, str] | None) -> str:
    if mode == "rank1_chase":
        return row.get("next_lever") or "update score, compare gap-to-#1, run one ablation/ensemble lever"
    if mode == "ceiling_refute_or_park":
        return "dispatch outside ceiling challenge; park only if no legal new lever survives"
    if mode == "unblock_data_or_auth_then_rank1_chase":
        return row.get("next_lever") or "clear credential/data gate, then create first scored baseline"
    if mode == "judge_satisfaction_iteration":
        if qrow and qrow.get("next_gate"):
            return qrow["next_gate"]
        return "run quality gate + outside judge critique; close P0 proof/story/polish gaps before submit"
    if mode == "monitor_award_or_edit_if_material_gap":
        return "monitor result; only edit/resubmit if material rubric gap or official feedback appears"
    return row.get("next_lever") or "recon rubric, eligibility, prize, and required artifact"


def render() -> str:
    rows = read_tsv(REGISTRY)
    qrows = {r["key"]: r for r in read_tsv(QUALITY) if r.get("key")}
    interesting = []
    for row in rows:
        key = row.get("key", "")
        status = row.get("status", "")
        if status in {"drop"}:
            continue
        lane = infer_lane(row, qrows)
        if status in {"submitted", "active", "ceiling", "blocked"} or lane == "leaderboard":
            mode = chase_mode(row, lane)
            qrow = qrows.get(key)
            interesting.append((lane, mode, row, qrow))

    order = {
        "rank1_chase": 0,
        "judge_satisfaction_iteration": 1,
        "unblock_data_or_auth_then_rank1_chase": 2,
        "ceiling_refute_or_park": 3,
        "monitor_award_or_edit_if_material_gap": 4,
    }
    interesting.sort(key=lambda x: (order.get(x[1], 9), -(int(x[2].get("progress") or 0))))

    lines = [
        "# Post-Submission Chase Board",
        "",
        "Submission is not done. Leaderboard entries chase rank-1; judged entries iterate until evaluator satisfaction or a kill rule.",
        "",
        "| mode | key | lane | status | progress | best | rank1 | gap | win% | next action |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for lane, mode, row, qrow in interesting:
        win = qrow.get("win_probability", "-") if qrow else "-"
        lines.append(
            "| {mode} | `{key}` | {lane} | {status} | {progress} | {best} | {rank1} | {gap} | {win} | {next} |".format(
                mode=mode,
                key=row.get("key", ""),
                lane=lane,
                status=row.get("status", ""),
                progress=row.get("progress", ""),
                best=row.get("best", "-"),
                rank1=row.get("rank1", "-"),
                gap=score_gap(row),
                win=win,
                next=(next_action(row, lane, mode, qrow) or "").replace("|", "/"),
            )
        )

    lines += [
        "",
        "## Rules",
        "",
        "- `submitted` is a monitoring/improvement state, not completion.",
        "- `ceiling` requires outside refutation before permanent park.",
        "- judged entries should not final-submit just because a portal accepts files.",
        "- every chase cycle must update score/evidence, next lever, and kill/continue rationale.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
