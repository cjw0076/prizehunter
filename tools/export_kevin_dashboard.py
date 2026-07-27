#!/usr/bin/env python3
"""Export prizehunter state into kevin8738/Dacon dashboard format.

Kevin's dashboard is git/static-site based. Its builder reads:

  competitions/<slug>/meta.json
  competitions/<slug>/policy.json
  competitions/<slug>/runs/*.jsonl

This bridge writes those files from the prizehunter portfolio registry, then
optionally runs the Kevin dashboard builder. It never exports credential values
or private lookup answers.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
QUALITY_TSV = CONTROL / "QUALITY_GATE_REPORT.tsv"
SUBMISSION_TSV = CONTROL / "SUBMISSION_BOARD.tsv"
FOUNDER_TSV = CONTROL / "FOUNDER_AUTH_DASHBOARD.tsv"
STRATEGY_MD = CONTROL / "STRATEGY_PLAYBOOK_BY_LANE.md"
CAP_REGISTRY = CONTROL / "capabilities" / "_registry.tsv"
TEAM_ROSTER_TSV = CONTROL / "TEAM_ROSTER.tsv"

VISIBLE_STATUSES = {
    "submitted",
    "active",
    "ready-gate",
    "blocked",
    "ceiling",
    "recon",
    "scaffold",
    "polishing",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="ignore", newline="") as f:
        lines = (line for line in f if line.strip() and not line.startswith("#"))
        return list(csv.DictReader(lines, delimiter="\t"))


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower()).strip("-")
    return slug or "competition"


def clean(text: str, max_len: int = 320) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    return s if len(s) <= max_len else s[: max_len - 3].rstrip() + "..."


def as_number(text: str) -> float | None:
    if text in {"", "-", "n/a", "none", None}:  # type: ignore[comparison-overlap]
        return None
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def metric_goal(direction: str) -> str:
    if direction == "min":
        return "minimize"
    if direction == "max":
        return "maximize"
    return "none"


def status_for_dashboard(status: str) -> str:
    # Kevin's current UI renders active/non-active badges only, but preserve the
    # exact status in tags and policy for humans.
    if status in {"submitted", "ceiling"}:
        return "done"
    return "active"


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def latest_ts() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


def default_target() -> Path | None:
    env = os.environ.get("KEVIN_DACON_REPO")
    candidates = [
        Path(env).expanduser() if env else None,
        Path("/tmp/kevin8738-dacon"),
        ROOT.parent / "Dacon",
        ROOT.parent / "dacon-dashboard",
    ]
    for c in candidates:
        if c and (c / "scripts" / "build_dashboard.js").exists() and (c / "site" / "app.js").exists():
            return c.resolve()
    return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stable_run(path: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Preserve existing run ts when only sync time changed.

    This keeps recurring team-dashboard syncs reviewable: material state changes
    still update files, but identical portfolio rows do not churn every
    competition run record.
    """
    if not path.exists():
        return run
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        old = json.loads(lines[-1]) if lines else {}
    except (OSError, json.JSONDecodeError):
        return run
    old_cmp = {k: v for k, v in old.items() if k != "ts"}
    new_cmp = {k: v for k, v in run.items() if k != "ts"}
    if old_cmp == new_cmp and old.get("ts"):
        out = dict(run)
        out["ts"] = old["ts"]
        return out
    return run


def build_payload(include_drop: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    registry = read_tsv(REGISTRY)
    quality = {r.get("key", ""): r for r in read_tsv(QUALITY_TSV)}
    submissions = {r.get("key", ""): r for r in read_tsv(SUBMISSION_TSV)}
    gates = read_tsv(FOUNDER_TSV)
    gates_by_key: dict[str, list[dict[str, str]]] = {}
    for gate in gates:
        gates_by_key.setdefault(gate.get("key", ""), []).append(gate)

    comps: list[dict[str, Any]] = []
    now = latest_ts()
    commit = git_hash()

    for row in registry:
        key = row.get("key", "")
        status = row.get("status", "")
        if not key:
            continue
        if status == "drop" and not include_drop:
            continue
        if status not in VISIBLE_STATUSES and not include_drop:
            continue

        q = quality.get(key, {})
        sub = submissions.get(key, {})
        best = as_number(row.get("best", ""))
        public_lb = best if status in {"submitted", "ceiling"} else None
        name = sub.get("name") or key
        lane = q.get("lane") or "prizehunter"
        gate = gates_by_key.get(key, [{}])[0]
        gate_request = gate.get("request", "")

        summary_parts = [
            f"status={status}",
            f"progress={row.get('progress', '-')}",
        ]
        if row.get("best") not in {"", "-"}:
            summary_parts.append(f"best={row.get('best')}")
        if row.get("rank1") not in {"", "-"}:
            summary_parts.append(f"rank1={row.get('rank1')}")
        if gate_request:
            summary_parts.append("gate=" + gate_request)
        elif row.get("next_lever"):
            summary_parts.append("next=" + row.get("next_lever", ""))

        official = sub.get("official") if sub.get("official") != "-" else ""
        tags = ["prizehunter", status, lane]
        if gate_request:
            tags.append("founder-gate")
        if q.get("ev_stance"):
            tags.append(q["ev_stance"].split(":", 1)[0].lower())

        run = {
            "ts": now,
            "agent": "prizehunter",
            "exp": "portfolio-sync",
            "cv": best,
            "public_lb": public_lb,
            "notes": clean(row.get("next_lever") or q.get("next_gate") or row.get("blocker")),
            "commit": commit,
            "submission": sub.get("project") if status == "submitted" else None,
        }

        comp = {
            "key": key,
            "slug": safe_slug(key),
            "name": name,
            "url": official,
            "status": status_for_dashboard(status),
            "raw_status": status,
            "deadline": "",
            "metric": row.get("metric") or "n/a",
            "metric_goal": metric_goal(row.get("direction", "")),
            "summary": clean("; ".join(summary_parts), 460),
            "data": row.get("ledger", ""),
            "tags": tags,
            "members": ["prizehunter", "codex", "claude"],
            "run": run,
            "policy": {
                "metric": row.get("metric") or "n/a",
                "metric_goal": metric_goal(row.get("direction", "")),
                "threshold": best,
                "margin": 0,
                "daily_limit": None,
                "today": {"date": datetime.now().date().isoformat(), "count": 0},
                "submitted_exps": ["portfolio-sync"] if status == "submitted" else [],
                "submissions": [
                    {
                        "date": datetime.now().date().isoformat(),
                        "exp": "portfolio-sync",
                        "cv": best,
                        "public_lb": public_lb,
                        "method": "external" if status == "submitted" else "manual",
                        "submission": sub.get("project") or sub.get("check") or "",
                        "msg": clean(sub.get("check") or row.get("blocker")),
                    }
                ]
                if status == "submitted"
                else [],
                "submit_api": {
                    "enabled": False,
                    "competition_id": None,
                    "note": "Managed by prizehunter; external auth gates remain outside git.",
                },
                "prizehunter": {
                    "progress": row.get("progress", ""),
                    "blocker": clean(row.get("blocker"), 500),
                    "next_lever": clean(row.get("next_lever"), 500),
                    "quality": q,
                    "founder_gates": gates_by_key.get(key, []),
                },
            },
        }
        comps.append(comp)

    summary = {
        "generated_at": latest_ts(),
        "source": "prizehunter-control-tower",
        "total_competitions": len(comps),
        "submitted": sum(c["raw_status"] == "submitted" for c in comps),
        "active": sum(c["raw_status"] == "active" for c in comps),
        "blocked": sum(c["raw_status"] in {"blocked", "ready-gate"} for c in comps),
        "founder_gates": len(gates),
    }
    return comps, gates, summary


def parse_strategy_playbook() -> list[dict[str, Any]]:
    if not STRATEGY_MD.exists():
        return []
    lanes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in STRATEGY_MD.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("## ") and not line.startswith("## Rules"):
            if current:
                lanes.append(current)
            current = {"lane": line[3:].strip(), "checklist": []}
            continue
        if not current:
            continue
        for key, label in [
            ("winning_thesis", "- winning thesis:"),
            ("required_proof", "- required proof:"),
            ("kill_rule", "- kill/park rule:"),
            ("agent_route", "- agent route:"),
        ]:
            if line.startswith(label):
                current[key] = line[len(label) :].strip()
        if line.startswith("- [ ] "):
            current.setdefault("checklist", []).append(line[6:].strip())
    if current:
        lanes.append(current)
    return lanes


def read_agent_roster() -> list[dict[str, str]]:
    rows = read_tsv(CAP_REGISTRY)
    out: list[dict[str, str]] = []
    for row in rows:
        agent = row.get("agent") or row.get("name") or ""
        if not agent or agent == "agent":
            continue
        out.append(
            {
                "agent": agent,
                "vendor": row.get("vendor", ""),
                "model": row.get("model", ""),
                "installed": row.get("installed", ""),
                "tier": row.get("tier", ""),
                "route_to": row.get("route_to", ""),
                "route_away": row.get("route_away", ""),
            }
        )
    seen = {row["agent"] for row in out}
    for row in read_tsv(TEAM_ROSTER_TSV):
        agent = row.get("agent", "")
        if not agent:
            continue
        item = {
            "agent": agent,
            "vendor": row.get("human_label", "team"),
            "model": row.get("role", ""),
            "installed": row.get("status", ""),
            "tier": "team",
            "route_to": row.get("route_to", ""),
            "route_away": row.get("notes", ""),
        }
        if agent in seen:
            for existing in out:
                if existing["agent"] == agent:
                    existing["team_role"] = row.get("role", "")
                    existing["human_label"] = row.get("human_label", "")
                    existing["team_status"] = row.get("status", "")
                    existing["team_notes"] = row.get("notes", "")
                    if row.get("route_to"):
                        existing["route_to"] = row["route_to"]
                    break
        else:
            out.append(item)
            seen.add(agent)
    return out


def build_team_workspace(comps: list[dict[str, Any]], gates: list[dict[str, str]], summary: dict[str, Any]) -> dict[str, Any]:
    quality = read_tsv(QUALITY_TSV)
    review_queue = sorted(
        (
            {
                "key": row.get("key", ""),
                "lane": row.get("lane", ""),
                "status": row.get("status", ""),
                "win_probability": row.get("win_probability", ""),
                "ev_stance": row.get("ev_stance", ""),
                "top_findings": row.get("top_findings", ""),
                "next_gate": row.get("next_gate", ""),
                "strategy_gaps": row.get("strategy_gaps", ""),
            }
            for row in quality
            if row.get("key")
        ),
        key=lambda r: int(float(r.get("win_probability") or 0)),
        reverse=True,
    )
    idea_board = [
        {
            "key": c["key"],
            "name": c["name"],
            "lane": next((t for t in c.get("tags", []) if t not in {"prizehunter", c.get("raw_status", "")}), ""),
            "status": c.get("raw_status", ""),
            "prompt": c.get("summary", ""),
            "ask_other_agents": (
                "Challenge the current approach, propose one cross-domain analogy, "
                "one high-risk/high-upside idea, and one kill criterion."
            ),
        }
        for c in comps
        if c.get("raw_status") in {"active", "ready-gate", "blocked"}
    ]
    return {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "roster": read_agent_roster(),
        "strategies": parse_strategy_playbook(),
        "review_queue": review_queue[:40],
        "idea_board": idea_board[:30],
        "communication": {
            "protocol": "append-only git comms",
            "message_path": "comms/<agent>/<YYYY-MM-DDThhmm>-<topic>.md",
            "run_path": "competitions/<slug>/runs/<agent>.jsonl",
            "repo": "https://github.com/kevin8738/Dacon",
            "dashboard_preview": "https://codex-prizehunter-team-dashboard-dacon.kevin873820.workers.dev/",
            "message_types": ["result", "question", "decision", "status", "handoff", "challenge", "idea"],
            "commands": [
                "export KEVIN_DACON_REPO=/path/to/Dacon",
                "competitions/control_tower/ph team init --target $KEVIN_DACON_REPO",
                "competitions/control_tower/ph team onboard --agent <agent> --human-label <label> --role <role> --route-to \"<best work>\" --target $KEVIN_DACON_REPO",
                "competitions/control_tower/ph team checkin --from <agent> --competition <key> --done \"<done>\" --next \"<next>\" --blocker \"<blocker>\"",
                "competitions/control_tower/ph team review --from <agent> --to <agent> --competition <key> --verdict challenge --body \"<critique>\"",
                "competitions/control_tower/ph team idea --from <agent> --competition <key> --topic \"<topic>\" --body \"<body>\"",
                "competitions/control_tower/ph kevin --target $KEVIN_DACON_REPO --build",
                "cd $KEVIN_DACON_REPO && git status && git add comms competitions site/data && git commit -m \"sync prizehunter team state\" && git push",
            ],
            "rules": [
                "Each agent writes only its own comms folder.",
                "Each human teammate uses a stable non-private agent alias; do not store phone, password, API token, or account details.",
                "Strategy changes must include evidence, counterargument, and next validation.",
                "Blocked work must record why it failed, how to retry, and which provider should challenge it.",
                "Founder/auth/spend/ToS gates are visible but secrets never enter git.",
            ],
        },
        "open_gates": gates,
    }


def write_sync_message(target: Path, summary: dict[str, Any]) -> None:
    body = (
        f"Synced {summary['total_competitions']} prizehunter competitions; "
        f"submitted={summary['submitted']}, active={summary['active']}, "
        f"blocked={summary['blocked']}, founder_gates={summary['founder_gates']}."
    )
    comms_dir = target / "comms" / "prizehunter"
    for existing in sorted(comms_dir.glob("*-sync.md")):
        try:
            if body in existing.read_text(encoding="utf-8", errors="ignore"):
                return
        except OSError:
            continue
    write_text(
        comms_dir / f"{datetime.now().strftime('%Y-%m-%dT%H%M')}-sync.md",
        "---\n"
        "from: prizehunter\n"
        "to: all\n"
        "competition: portfolio\n"
        "type: sync\n"
        f"ts: {latest_ts()}\n"
        "---\n"
        f"{body}\n",
    )


def export(target: Path, include_drop: bool, build: bool) -> int:
    if not (target / "scripts" / "build_dashboard.js").exists():
        raise SystemExit(f"target is not a Kevin dashboard repo: {target}")

    comps, gates, summary = build_payload(include_drop=include_drop)
    team_workspace = build_team_workspace(comps, gates, summary)
    for comp in comps:
        comp_dir = target / "competitions" / comp["slug"]
        run_path = comp_dir / "runs" / "prizehunter.jsonl"
        meta = {k: comp[k] for k in ["slug", "name", "url", "status", "deadline", "metric", "metric_goal", "summary", "data", "tags", "members"]}
        meta["prizehunter_key"] = comp["key"]
        meta["raw_status"] = comp["raw_status"]
        write_json(comp_dir / "meta.json", meta)
        write_json(comp_dir / "policy.json", comp["policy"])
        write_text(run_path, json.dumps(stable_run(run_path, comp["run"]), ensure_ascii=False) + "\n")

    write_json(target / "site" / "data" / "prizehunter_summary.json", summary)
    write_json(target / "site" / "data" / "founder_gates.json", gates)
    write_json(target / "site" / "data" / "team_workspace.json", team_workspace)
    write_sync_message(target, summary)

    if build:
        subprocess.run(["node", "scripts/build_dashboard.js"], cwd=target, check=True)

    print(f"exported {len(comps)} competitions to {target}")
    print(f"founder gates exported: {len(gates)}")
    if not build:
        print("next -> run `node scripts/build_dashboard.js` in the Kevin dashboard repo, then git diff/commit/push")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", help="Path to kevin8738/Dacon checkout. Defaults to KEVIN_DACON_REPO or /tmp/kevin8738-dacon.")
    parser.add_argument("--include-drop", action="store_true", help="Also export dropped contests.")
    parser.add_argument("--build", action="store_true", help="Run Kevin dashboard build after export.")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve() if args.target else default_target()
    if not target:
        raise SystemExit("No dashboard checkout found. Clone it first or set KEVIN_DACON_REPO=/path/to/Dacon.")
    return export(target, include_drop=args.include_drop, build=args.build)


if __name__ == "__main__":
    raise SystemExit(main())
