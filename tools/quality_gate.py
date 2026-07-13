#!/usr/bin/env python3
"""Quality and EV gate for prizehunter.

This is the anti-"high win-rate trap" layer. It checks whether a package is
actually judge-ready, not just quickly assembled. It also writes lane-specific
strategy guidance so cross-domain competitions do not all receive the same
generic build workflow.
"""
from __future__ import annotations

import csv
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"
POOL = CONTROL / "NEXT_COMPETITION_POOL.tsv"
OUT_MD = CONTROL / "QUALITY_GATE_REPORT.md"
OUT_TSV = CONTROL / "QUALITY_GATE_REPORT.tsv"
PLAYBOOK = CONTROL / "STRATEGY_PLAYBOOK_BY_LANE.md"
PACKAGES = CONTROL / "EXIT" / "packages"


LANE_PATTERNS = {
    "leaderboard": r"kaggle|dacon|leaderboard|accuracy|logloss|nmae|ml|알고리즘|예측",
    "hackathon": r"hackathon|해커톤|devpost|앱|웹|sw|software",
    "publicdata_product": r"공공데이터|data\.go\.kr|데이터.*창업|제품|서비스|산업통상|부산",
    "creative_media": r"영상|ucc|film|media|디자인|웹툰|포스터|광고|art|미술|창작",
    "text_literature": r"문학|독후감|poetry|story|fiction|essay|수기|글쓰기",
    "idea_design": r"아이디어|기획|건축|invention|design|제안|future|techbriefs",
}


STRATEGIES = {
    "leaderboard": {
        "winning_thesis": "Only trust honest CV/public-private transfer, not public rank or lucky submissions.",
        "proof": "OOF/CV ledger, ablation, adversarial split, submit-economy log, ceiling-refutation by another agent.",
        "kill_rule": "Park when gap-to-#1 needs unavailable model/data or luck-mining starts degrading generalization.",
        "next_agent": "Codex/local LLM for experiments; Claude/Gemini for ceiling challenge.",
    },
    "hackathon": {
        "winning_thesis": "A working hosted demo with a tight story beats a broad but shallow agent.",
        "proof": "Public repo, license, hosted demo, 2-minute video, logs/screenshots, judging-rubric mapping.",
        "kill_rule": "Kill when signup/ToS/spend/API gates exceed prize EV or the core integration is unavailable.",
        "next_agent": "Codex for build/deploy; design/visual QA before submit; founder for ToS/final submit.",
    },
    "publicdata_product": {
        "winning_thesis": "Judges reward real public-data dependency, operational adoption, and defensible impact math.",
        "proof": "Official rule block, source row counts, runnable demo/source, methodology appendix, user validation.",
        "kill_rule": "Park if it is a thin dashboard/reskin, has no real beneficiary, or founder-local burden is high.",
        "next_agent": "Codex for data/prototype/evidence; Claude for proposal coherence; founder for validation/signature.",
    },
    "creative_media": {
        "winning_thesis": "Taste and first-glance originality dominate; technical process matters only if visible.",
        "proof": "Final media, storyboard, visual references, rights/AI-policy check, multiple variants, external critique.",
        "kill_rule": "Kill if rules prohibit AI/generative workflow or if production time is high with low prize.",
        "next_agent": "Creative/visual agents for variants; Codex for rights/package QA.",
    },
    "text_literature": {
        "winning_thesis": "Generic writing loses; the angle must match the judge's hidden taste and rules on AI use.",
        "proof": "Official AI-use policy, final manuscript, originality note, revision trail, human editorial pass.",
        "kill_rule": "Kill if AI use is forbidden and the founder will not personally author/review.",
        "next_agent": "Claude/Gemini for editorial critique; Codex only for rule/evidence tracking.",
    },
    "idea_design": {
        "winning_thesis": "A proposal wins when it looks implementable: diagram, budget, stakeholder map, impact metric.",
        "proof": "Concept board, prototype/mockup, cost model, adoption plan, precedent research, risk register.",
        "kill_rule": "Kill if the idea remains a slogan without a specific buyer/operator and measurable outcome.",
        "next_agent": "Codex for research/evidence; visual/design agent for boards; Claude for narrative.",
    },
    "other": {
        "winning_thesis": "Do not commit until the competition type, prize, eligibility, and deliverable are explicit.",
        "proof": "Official rules, prize, deadline, eligibility, deliverable list, founder gates.",
        "kill_rule": "Default to recon/park.",
        "next_agent": "Codex recon.",
    },
}

STRATEGY_CHECKS = {
    "leaderboard": [
        ("honest CV/OOF ledger", [r"\bcv\b", r"\boof\b", r"cross[- ]?validation", r"검증"], []),
        ("ablation or error-family proof", [r"ablation", r"error family", r"오류", r"실험"], []),
        ("submit-economy / anti-luck rule", [r"submit", r"submission", r"luck", r"ceiling", r"overfit", r"도박"], []),
        ("outside ceiling challenge", [r"challenge", r"refut", r"claude", r"gemini", r"review"], []),
    ],
    "hackathon": [
        ("public repo/license proof", [r"repo", r"github", r"license"], []),
        ("hosted or runnable demo proof", [r"hosted", r"demo", r"devpost", r"live"], [r"index\.html", r"demo"]),
        ("video/deck/story proof", [r"video", r"youtube", r"slides", r"deck"], [r"slides", r"storyboard", r"\.mp4$"]),
        ("rubric mapping", [r"rubric", r"judg", r"criteria", r"평가"], []),
    ],
    "publicdata_product": [
        ("official rule/eligibility block", [r"official", r"rules?", r"공모요강", r"eligib", r"자격"], []),
        ("public-data provenance", [r"data\.go\.kr", r"public data", r"source", r"provenance", r"공공데이터"], [r"data_sources", r"sources"]),
        ("runnable demo/source", [r"runnable", r"demo", r"source", r"cli"], [r"index\.html", r"offline_demo", r"\.py$"]),
        ("defensible impact math", [r"methodology", r"savings", r"benefit", r"impact", r"절감", r"편익"], [r"methodology"]),
        ("real user/operator validation", [r"walkthrough", r"user validation", r"operator", r"real validation", r"사용자 검증"], [r"real_walkthrough"]),
    ],
    "creative_media": [
        ("final media or storyboard", [r"storyboard", r"final", r"visual"], [r"\.mp4$", r"\.mov$", r"\.png$", r"\.jpg$", r"storyboard"]),
        ("rights / AI-use policy", [r"rights", r"license", r"ai use", r"저작권", r"생성형"], []),
        ("multiple variants / critique", [r"variant", r"critique", r"review", r"external"], []),
        ("first-glance concept hook", [r"hook", r"concept", r"taste", r"컨셉"], []),
    ],
    "text_literature": [
        ("AI-use/originality policy", [r"ai.*금지", r"ai use", r"originality", r"표절", r"저작"], []),
        ("final manuscript", [r"manuscript", r"essay", r"draft", r"본문"], [r"manuscript", r"essay", r"\.pdf$"]),
        ("revision/editorial trail", [r"revision", r"editor", r"critique", r"퇴고"], []),
        ("judge-taste angle", [r"judge", r"taste", r"theme", r"심사"], []),
    ],
    "idea_design": [
        ("specific operator/buyer", [r"operator", r"stakeholder", r"buyer", r"persona", r"수요자"], []),
        ("diagram/mockup/prototype", [r"diagram", r"mockup", r"prototype", r"wireframe"], [r"\.png$", r"\.jpg$", r"prototype"]),
        ("budget/cost model", [r"budget", r"cost", r"price", r"비용", r"예산"], []),
        ("impact metric and risk register", [r"impact", r"metric", r"risk", r"kpi", r"효과"], []),
    ],
    "other": [
        ("official rules", [r"official", r"rules?", r"공모요강"], []),
        ("prize/deadline/eligibility", [r"prize", r"deadline", r"eligib", r"상금", r"마감", r"자격"], []),
        ("explicit deliverables", [r"deliverable", r"submission", r"제출"], []),
    ],
}


MANUAL_OVERRIDES: dict[str, dict] = {}  # per-competition manual gate overrides; populate for your own comps

# Empty in the shipped product: lanes are inferred from LANE_PATTERNS against the
# registry row (see lane_for). Add your own keys here only to pin a lane, e.g.
# LANE_OVERRIDES = {"example-comp": "leaderboard"}.
LANE_OVERRIDES: dict[str, str] = {}


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="ignore") as f:
        rows = csv.DictReader(
            (
                line
                for line in f
                if line.strip() and not line.lstrip().lstrip('"').startswith("#")
            ),
            delimiter="\t",
        )
        return [{k: (v or "") for k, v in row.items()} for row in rows]


def lane_for(row: dict[str, str]) -> str:
    if row.get("key") in LANE_OVERRIDES:
        return LANE_OVERRIDES[row.get("key", "")]
    blob = " ".join(
        row.get(k, "")
        for k in ["key", "name", "dir", "metric", "status", "blocker", "next_lever", "kind", "source", "note"]
    ).lower()
    for lane, pat in LANE_PATTERNS.items():
        if re.search(pat, blob, flags=re.I):
            return lane
    return "other"


def latest_package(key: str) -> Path | None:
    files = sorted(PACKAGES.glob(f"{key}_submission_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def zip_entries(path: Path | None) -> list[str]:
    if not path:
        return []
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    except Exception:
        return []


def text_sample(campdir: Path) -> str:
    chunks: list[str] = []
    package_dir = campdir / "submission_package"
    patterns = ["submission_package/*.md"] if package_dir.exists() else ["*.md", "deliverables/*.md"]
    for pat in patterns:
        for p in sorted(campdir.glob(pat))[:40]:
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="ignore")[:4000])
            except Exception:
                pass
    return "\n".join(chunks)


def has_any(entries: list[str], patterns: list[str]) -> bool:
    return any(re.search(p, entry, flags=re.I) for entry in entries for p in patterns)


def strategy_gaps(lane: str, entries: list[str], lower: str) -> list[str]:
    gaps: list[str] = []
    for label, text_patterns, entry_patterns in STRATEGY_CHECKS.get(lane, STRATEGY_CHECKS["other"]):
        text_ok = any(re.search(p, lower, flags=re.I) for p in text_patterns)
        entry_ok = has_any(entries, entry_patterns) if entry_patterns else False
        if not (text_ok or entry_ok):
            gaps.append(label)
    return gaps


def package_findings(key: str, lane: str, campdir: Path, row: dict[str, str]) -> tuple[list[str], int, int]:
    findings: list[str] = []
    score_sub = 35
    score_judge = 30
    pkg = latest_package(key)
    entries = zip_entries(pkg)
    sample = text_sample(campdir)
    lower = sample.lower()

    if campdir.exists():
        score_sub += 10
    else:
        findings.append("campaign folder missing")
    if (campdir / "WORKLOG.md").exists() or (campdir / "AGENT_WORKLOG.md").exists():
        score_judge += 5
    if pkg and entries:
        score_sub += 15
    else:
        findings.append("no local submission package found")

    if re.search(r"\.\.\.|TODO|fill:|paste-ready|placeholder|intentionally blank", sample, flags=re.I):
        findings.append("draft/placeholders remain in package docs")
        score_sub -= 8
        score_judge -= 6

    if lane == "publicdata_product":
        if has_any(entries, [r"proposal.*\.pdf", r"기획서", r"proposal.*\.md"]):
            score_sub += 8
        else:
            findings.append("proposal artifact missing from latest package")
        if has_any(entries, [r"site/index\.html", r"demo.*\.html", r"index\.html"]):
            score_sub += 9
            score_judge += 8
        else:
            findings.append("latest package lacks a runnable/offline demo HTML")
        if has_any(entries, [r"data_sources\.md", r"source", r"site-data\.json", r"data\.json"]):
            score_judge += 8
        else:
            findings.append("data/provenance evidence missing from package")
        if "proxy validation" in lower or "proxy-ready" in lower:
            findings.append("user validation is proxy-only")
            score_judge -= 8
        if re.search(r"rank-1|leaderboard|honest-cv|leak-checked|overfit", lower):
            findings.append("leaderboard-template language found in judged product docs")
            score_judge -= 8

    elif lane == "leaderboard":
        if re.search(r"cv|oof|ablation|submission|leaderboard", lower):
            score_judge += 14
        else:
            findings.append("leaderboard evidence/CV ledger not obvious")
        if "ceiling" in row.get("status", "") or "ceiling" in lower:
            findings.append("ceiling/luck-mining risk must be refuted before more spend")
            score_judge -= 6

    elif lane == "hackathon":
        for label, pats in {
            "repo/license": [r"repo", r"license"],
            "hosted demo": [r"demo", r"hosted", r"devpost"],
            "video/deck": [r"video", r"youtube", r"slides", r"deck"],
        }.items():
            if re.search("|".join(pats), lower):
                score_judge += 5
            else:
                findings.append(f"{label} proof not obvious")

    elif lane == "creative_media":
        if re.search(r"rights|license|ai use|저작권|생성형", lower):
            score_judge += 6
        else:
            findings.append("rights/AI-policy proof missing")
        if has_any(entries, [r"\.mp4$", r"\.mov$", r"\.png$", r"\.jpg$", r"storyboard"]):
            score_sub += 8
        else:
            findings.append("final visual/media artifact not obvious")

    elif lane == "text_literature":
        if re.search(r"ai.*금지|ai use|originality|표절|저작", lower):
            score_judge += 6
        else:
            findings.append("AI-use/originality policy not recorded")
        if has_any(entries, [r"manuscript", r"essay", r"draft", r"\.pdf$"]):
            score_sub += 7
        else:
            findings.append("final manuscript artifact missing")

    elif lane == "idea_design":
        if re.search(r"budget|cost|stakeholder|prototype|mockup|impact", lower):
            score_judge += 8
        else:
            findings.append("implementation/budget/impact proof missing")

    if "founder" in (row.get("blocker", "") + row.get("next_lever", "")).lower():
        findings.append("founder gate remains; do not call externally ready")
        score_sub -= 6
    if row.get("status") in {"drop", "ceiling"}:
        score_judge = min(score_judge, 35)

    gaps = strategy_gaps(lane, entries, lower)
    for gap in gaps[:4]:
        findings.append(f"strategy gap: {gap}")
    score_judge -= min(18, 4 * len(gaps))
    return findings, clamp(score_sub), clamp(score_judge)


def has_real_walkthrough(campdir: Path) -> bool:
    checker = campdir / "tools" / "check_walkthroughs.py"
    if not checker.exists():
        return False
    try:
        subprocess.check_output(["python3", str(checker)], text=True, stderr=subprocess.STDOUT, timeout=5)
        return True
    except Exception:
        return False


def clamp(v: int) -> int:
    return max(0, min(100, int(v)))


def build_rows() -> list[dict[str, str]]:
    rows = []
    for r in read_tsv(REGISTRY):
        key = r.get("key", "")
        if not key or key == "key":
            continue
        campdir = ROOT / r.get("dir", "")
        lane = MANUAL_OVERRIDES.get(key, {}).get("lane") or lane_for(r)
        findings, sub_ready, judge_quality = package_findings(key, lane, campdir, r)
        pkg = latest_package(key)
        entries = zip_entries(pkg)
        gaps = strategy_gaps(lane, entries, text_sample(campdir).lower())
        if lane == "publicdata_product" and not has_real_walkthrough(campdir):
            real_gap = "real user/operator validation (no accepted walkthrough row)"
            gaps = [real_gap] + [g for g in gaps if g != "real user/operator validation"]
        winp = clamp(round(judge_quality * 0.55 + sub_ready * 0.20))
        ev = "UNKNOWN"
        prize = 0
        try:
            prize = int(r.get("prize_krw", "0") or 0)
        except Exception:
            prize = 0

        if key in MANUAL_OVERRIDES:
            ov = MANUAL_OVERRIDES[key]
            sub_ready = ov["submission_readiness"]
            judge_quality = ov["judge_quality"]
            winp = ov["win_probability"]
            ev = ov["ev_stance"]
            findings = ov["forced_findings"] + [f for f in findings if f not in ov["forced_findings"]]
            next_gate = ov["next_gate"]
        else:
            strategy = STRATEGIES[lane]
            next_gate = r.get("next_lever") or strategy["proof"]
            if r.get("status") in {"drop", "ceiling"}:
                ev = "LOW/PARK"
            elif prize:
                ev = "HIGH" if prize * winp / 100 >= 10_000_000 else "MEDIUM" if winp >= 25 else "LOW"
            elif r.get("status") in {"active", "submitted", "ready-gate"}:
                ev = "EVIDENCE-BOUND"

        rows.append(
            {
                "key": key,
                "lane": lane,
                "status": r.get("status", ""),
                "progress": r.get("progress", ""),
                "submission_readiness": str(sub_ready),
                "judge_quality": str(judge_quality),
                "win_probability": str(winp),
                "ev_stance": ev,
                "top_findings": "; ".join(findings[:4]) or "no critical finding from automated scan",
                "next_gate": next_gate,
                "strategy_gaps": "; ".join(gaps[:4]) or "none detected by lane gate",
            }
        )
    return sorted(rows, key=lambda r: (int(r["win_probability"]), int(r["judge_quality"])), reverse=True)


def write_playbook() -> None:
    with PLAYBOOK.open("w", encoding="utf-8") as f:
        f.write("# Strategy Playbook By Lane\n\n")
        f.write(f"_generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')} · source: `tools/quality_gate.py`_\n\n")
        f.write("Use this before assigning agents. Diverse competitions need different proof, not the same package template.\n\n")
        for lane, s in STRATEGIES.items():
            f.write(f"## {lane}\n\n")
            f.write(f"- winning thesis: {s['winning_thesis']}\n")
            f.write(f"- required proof: {s['proof']}\n")
            f.write(f"- kill/park rule: {s['kill_rule']}\n")
            f.write(f"- agent route: {s['next_agent']}\n\n")
            f.write("quality checklist:\n")
            for label, _, _ in STRATEGY_CHECKS.get(lane, STRATEGY_CHECKS["other"]):
                f.write(f"- [ ] {label}\n")
            f.write("\n")


def write_report(rows: list[dict[str, str]]) -> None:
    cols = [
        "key",
        "lane",
        "status",
        "progress",
        "submission_readiness",
        "judge_quality",
        "win_probability",
        "ev_stance",
        "top_findings",
        "next_gate",
        "strategy_gaps",
    ]
    with OUT_TSV.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(r[c].replace("\n", " ") for c in cols) + "\n")

    with OUT_MD.open("w", encoding="utf-8") as f:
        f.write("# Quality Gate Report\n\n")
        f.write(f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}\n")
        f.write("- stance: expected-value control, not activity tracking\n")
        f.write("- rule: progress is package/build progress; it is not win probability\n\n")
        f.write("## Active / Highest-Signal Rows\n\n")
        f.write("| win% | judge | submit | status | lane | key | EV | findings | next gate | strategy gaps |\n")
        f.write("|---:|---:|---:|---|---|---|---|---|---|---|\n")
        interesting = [
            r
            for r in rows
            if r["status"] in {"active", "submitted", "ready-gate", "blocked", "ceiling"}
            or r["key"] in MANUAL_OVERRIDES
        ]
        for r in interesting[:45]:
            f.write(
                f"| {r['win_probability']} | {r['judge_quality']} | {r['submission_readiness']} | "
                f"{r['status']} | {r['lane']} | `{r['key']}` | {r['ev_stance']} | "
                f"{r['top_findings']} | {r['next_gate']} | {r['strategy_gaps']} |\n"
            )
        f.write("\n## Operating Rules\n\n")
        f.write("1. A package cannot be called final while official forms, signature, ToS, account, spend, or external submit remain open.\n")
        f.write("2. A judged product package must include a runnable artifact or public demo proof, not only a screenshot.\n")
        f.write("3. A claimed financial benefit must distinguish modeled savings, opportunity, and guaranteed cash.\n")
        f.write("4. A creative/media/text entry must pass rights and AI-use policy checks before production spend.\n")
        f.write("5. Low-EV tracks are parked even if they are easy to submit.\n")
        f.write("6. `ph strategy` is the canonical lane playbook; update `tools/quality_gate.py` when a new competition type appears.\n")
        f.write("\nSee also: `STRATEGY_PLAYBOOK_BY_LANE.md`.\n")


def main() -> None:
    rows = build_rows()
    write_report(rows)
    write_playbook()
    print(OUT_MD)
    print(OUT_TSV)
    print(PLAYBOOK)
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
