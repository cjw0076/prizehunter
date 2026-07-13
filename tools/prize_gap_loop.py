#!/usr/bin/env python3
"""Generate a contest-specific prize gap loop.

The goal is not "meet requirements". The goal is to find what the judges or
leaderboard actually reward, expose where our current approach is weak, and
turn that into a 120%+ iteration backlog.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


CONTROL = Path(__file__).resolve().parents[1]
ROOT = CONTROL.parents[1]
REGISTRY = CONTROL / "portfolio_registry.tsv"


ARCHETYPES = {
    "leaderboard": {
        "label": "Leaderboard / DACON / Kaggle",
        "triggers": ["dacon", "kaggle", "leaderboard", "metric", "데이터", "경진대회", "classification", "regression"],
        "judge_needs": [
            "Hidden intent behind the metric, not just high public score.",
            "Private-leaderboard robustness and distribution-shift discipline.",
            "Data semantics: why each feature/target exists and what would generalize.",
            "Leakage awareness, honest CV, ablation evidence, and submission-economy control.",
            "Creative problem reframing when direct modeling saturates.",
        ],
        "common_deficiencies": [
            "Public leaderboard overfit; private split is treated as an afterthought.",
            "Feature engineering is mechanical, not tied to domain semantics.",
            "No adversarial validation or public/private shift hypothesis.",
            "No kill criteria for luck-mining or local-CV/public mismatch.",
            "Winning intent is guessed once instead of re-mined every iteration.",
        ],
        "responses_120": [
            "Build a hidden-intent dossier: metric nonlinearity, split clues, organizer examples, and rank-1 behavior.",
            "Maintain honest CV, adversarial validation, error slices, leakage checks, and public-anchor calibration.",
            "Run model/feature experiments as hypotheses with receipts: what changed, why, and which slice improved.",
            "Use a submission ledger: expected delta, risk, daily-limit cost, and rollback candidate.",
            "Ask a side agent to refute every ceiling claim before stopping.",
        ],
        "evidence": [
            "official metric/rules/daily-limit page",
            "baseline and rank-1 public behavior",
            "CV vs public correlation table",
            "error-slice report",
            "feature/leakage audit",
        ],
    },
    "idea_business": {
        "label": "Idea / Business / Public Policy",
        "triggers": ["idea", "아이디어", "창업", "사업화", "정책", "제안", "공공데이터", "활용 사례"],
        "judge_needs": [
            "A problem that feels newly discovered, urgent, and owner-specific.",
            "Feasible execution path, stakeholder map, budget, rollout, and legal/operational constraints.",
            "Business or policy impact with measurable KPIs.",
            "Prototype or demo proving it is more than a concept.",
            "Visual clarity: one glance should communicate the product and its value.",
        ],
        "common_deficiencies": [
            "The idea stops at a slogan or generic AI wrapper.",
            "No proof that the target user, buyer, or public agency would adopt it.",
            "No MVP, no workflow, no data provenance, no budget, no risk plan.",
            "Weak naming/brand/visuals make the submission look like a school report.",
            "Impact is emotional but not measurable.",
        ],
        "responses_120": [
            "Ship a clickable prototype or working demo with real/public data where possible.",
            "Add business model, operating plan, pilot roadmap, KPI dashboard, and procurement/adoption path.",
            "Include stakeholder interviews or proxy evidence when direct interviews are impossible.",
            "Create a brand/character/visual system and polished submission screenshots.",
            "Attach a feasibility appendix: data sources, architecture, cost, risks, and mitigation.",
        ],
        "evidence": [
            "official rubric",
            "previous winners and organizer press releases",
            "stakeholder/user map",
            "prototype screenshots or live demo",
            "KPI and feasibility appendix",
        ],
    },
    "design_media": {
        "label": "Design / Media / Character / Webtoon / Video",
        "triggers": ["design", "디자인", "영상", "미디어", "웹툰", "캐릭터", "창작", "브랜드", "아트"],
        "judge_needs": [
            "A memorable visual identity that fits the theme and judging context.",
            "Craft: composition, typography, color, story beat, and production finish.",
            "Originality without losing brief compliance.",
            "Portfolio-grade presentation assets, not just final files.",
            "Rights-safe references and asset provenance.",
        ],
        "common_deficiencies": [
            "Looks generic or template-driven.",
            "No character/brand system; only a one-off image or video.",
            "Visual references are not curated or rights-safe.",
            "No storyboard, moodboard, rationale, or production notes.",
            "Mobile/thumbnail/first-glance impact is untested.",
        ],
        "responses_120": [
            "Build a visual bible: logo/wordmark, palette, type, character cues, shot language, and do/don't examples.",
            "Prepare moodboard, storyboard, key visuals, thumbnails, and final presentation board.",
            "Run visual QA across desktop/mobile/thumbnail and ensure text does not overlap.",
            "Show iteration history and why the final direction wins the brief.",
            "Record source licenses and AI-use constraints.",
        ],
        "evidence": [
            "brief/rubric/theme text",
            "moodboard and references",
            "visual bible",
            "storyboard/key frames",
            "asset provenance",
        ],
    },
    "literature": {
        "label": "Literature / Essay / Story",
        "triggers": ["문학", "문예", "에세이", "독후감", "소설", "시", "스토리", "시나리오"],
        "judge_needs": [
            "A distinctive voice and finished manuscript quality.",
            "Fit to the contest's theme, audience, and past selections.",
            "Author credibility: bio, publication/activity record, portfolio, and intent.",
            "Revision discipline: structure, rhythm, originality, and line-level polish.",
            "Rights clarity and submission-format compliance.",
        ],
        "common_deficiencies": [
            "A competent draft without a recognizable voice.",
            "No author record, portfolio page, activity log, or literary positioning.",
            "Theme compliance is literal, not transformed into a strong premise.",
            "No editorial passes or outside-reader critique.",
            "Formatting and rights statements are treated as clerical details.",
        ],
        "responses_120": [
            "Create author dossier: bio, activity record, prior/public portfolio, statement, and relevance to theme.",
            "Build a contest-fit dossier: past winners, judges, tone, length, and taboo patterns.",
            "Run three-pass editing: macro structure, scene/argument flow, line polish.",
            "Get side-agent outside-reader critique for originality and emotional residue.",
            "Package manuscript, author note, portfolio links, and compliance checklist together.",
        ],
        "evidence": [
            "past winner samples or summaries",
            "author bio/activity log",
            "portfolio index",
            "revision log",
            "format/compliance checklist",
        ],
    },
    "art_culture": {
        "label": "Art / Culture / Exhibition",
        "triggers": ["예술", "미술", "전시", "문화", "공연", "음악", "콩쿠르", "댄스"],
        "judge_needs": [
            "Conceptual statement with cultural relevance and coherent craft.",
            "Portfolio history and activity record.",
            "Installation/presentation feasibility.",
            "Audience or community impact where relevant.",
            "Rights, materials, budget, and production readiness.",
        ],
        "common_deficiencies": [
            "Concept statement is vague or fashionable but not grounded.",
            "Portfolio does not explain trajectory or why this work matters now.",
            "No production plan, installation spec, or budget.",
            "References are aesthetic only, not conceptual.",
        ],
        "responses_120": [
            "Create artist dossier: statement, CV/activity log, portfolio sequence, and work notes.",
            "Prepare exhibition-ready presentation board and install/mockup images.",
            "Add materials, budget, schedule, risk, and audience plan.",
            "Map references to concept, not just style.",
        ],
        "evidence": [
            "artist CV/activity log",
            "portfolio board",
            "concept statement",
            "installation or production plan",
            "budget/risk sheet",
        ],
    },
    "hackathon": {
        "label": "Hackathon / Prototype / Developer Challenge",
        "triggers": ["hackathon", "해커톤", "devpost", "개발", "서비스", "agent", "앱", "prototype"],
        "judge_needs": [
            "Working demo with a clear product story.",
            "Use of required platform/API in a central, not decorative, way.",
            "Technical credibility: repo, tests, architecture, deployment path.",
            "Impact narrative and user workflow.",
            "Demo video/deck that make the system legible in minutes.",
        ],
        "common_deficiencies": [
            "Demo is a mockup with no real workflow.",
            "Sponsor API is bolted on rather than central.",
            "No tests, setup, deployment, or failure-mode story.",
            "Visuals and video undersell the artifact.",
        ],
        "responses_120": [
            "Ship a runnable prototype with seed data, tests, and one-command demo.",
            "Make the sponsor/platform integration indispensable to the core loop.",
            "Create demo script, video storyboard, screenshots, and architecture diagram.",
            "Add reliability/failure-mode notes and user value evidence.",
        ],
        "evidence": [
            "repo and smoke tests",
            "live/demo URL or local run receipt",
            "architecture diagram",
            "demo video storyboard",
            "sponsor API proof",
        ],
    },
}


def norm(text: str) -> str:
    return (text or "").lower()


def detect_archetypes(name: str, platform: str, domain: str, explicit: str) -> list[str]:
    if explicit:
        return [x.strip() for x in explicit.split(",") if x.strip() in ARCHETYPES]
    blob = norm(" ".join([name, platform, domain]))
    hits: list[str] = []
    for key, spec in ARCHETYPES.items():
        if any(norm(t) in blob for t in spec["triggers"]):
            hits.append(key)
    if "leaderboard" not in hits and any(x in blob for x in ["dacon", "kaggle", "metric"]):
        hits.insert(0, "leaderboard")
    return hits or ["idea_business"]


def registry_campaign_dir(key: str) -> Path | None:
    if not REGISTRY.exists():
        return None
    header: list[str] | None = None
    for line in REGISTRY.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        row = dict(zip(header, parts))
        if row.get("key") == key and row.get("dir"):
            return ROOT / row["dir"]
    return None


def task_rows(keys: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in keys:
        spec = ARCHETYPES[key]
        rows.extend(
            [
                {
                    "priority": "P0",
                    "need": f"{spec['label']} judge-intent dossier",
                    "deficiency_test": "Can we state what first place proves beyond the written requirement?",
                    "response_120": spec["responses_120"][0],
                    "owner": "Codex",
                    "status": "todo",
                },
                {
                    "priority": "P0",
                    "need": "Evidence/provenance pack",
                    "deficiency_test": "Are rules, prior winners, references, data, and asset rights source-backed?",
                    "response_120": "Collect and cite: " + "; ".join(spec["evidence"][:4]),
                    "owner": "Codex",
                    "status": "todo",
                },
                {
                    "priority": "P1",
                    "need": "Build-quality uplift",
                    "deficiency_test": "Would this still stand out if every competitor met the official checklist?",
                    "response_120": spec["responses_120"][1],
                    "owner": "Claude",
                    "status": "todo",
                },
                {
                    "priority": "P1",
                    "need": "Adversarial challenge",
                    "deficiency_test": "What would a skeptical judge or public/private split punish?",
                    "response_120": "Dispatch Gemini/side agent to attack assumptions and propose stronger routes.",
                    "owner": "Gemini",
                    "status": "todo",
                },
            ]
        )
    rows.append(
        {
            "priority": "P0",
            "need": "120% delta ledger",
            "deficiency_test": "Is the delta from 100% to 120% visible in the final package?",
            "response_120": "Maintain a before/after checklist: required deliverable vs extra proof, prototype, visual, portfolio, or validation.",
            "owner": "Claude+Codex",
            "status": "todo",
        }
    )
    return rows


def md_for(key: str, name: str, platform: str, domain: str, url: str, archetype_keys: list[str], rows: list[dict[str, str]]) -> str:
    lines = [
        f"# Prize Gap Loop — {name}",
        "",
        f"- key: `{key}`",
        f"- platform: {platform or 'TBD'}",
        f"- domain: {domain or 'TBD'}",
        f"- official_url: {url or 'TBD'}",
        f"- generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}",
        "",
        "## Principle",
        "",
        "The target is not compliance. If the contest asks for 100%, prizehunter must expose what 100% misses and produce 120%+ evidence: hidden intent, feasibility, portfolio/history, prototype, visual system, validation, and receipts.",
        "",
        "## Detected Contest Needs",
        "",
    ]
    for ak in archetype_keys:
        spec = ARCHETYPES[ak]
        lines += [f"### {spec['label']}", "", "**What they likely need**"]
        lines += [f"- {x}" for x in spec["judge_needs"]]
        lines += ["", "**Common ways we would lose**"]
        lines += [f"- {x}" for x in spec["common_deficiencies"]]
        lines += ["", "**120%+ response**"]
        lines += [f"- {x}" for x in spec["responses_120"]]
        lines += [""]

    lines += [
        "## Iteration Backlog",
        "",
        "| priority | need | deficiency test | 120%+ response | owner | status |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['priority']} | {row['need']} | {row['deficiency_test']} | {row['response_120']} | {row['owner']} | {row['status']} |"
        )

    lines += [
        "",
        "## Operating Loop",
        "",
        "1. Codex writes/updates `CREATIVE_BRIEF.md` from this gap loop.",
        "2. Gemini or another sidecar attacks the brief before build.",
        "3. Claude builds the artifact package and marks which 120% gaps were closed.",
        "4. Codex/Claude review the final package against this file before founder-gated submission.",
        "5. `record_asset_receipt.sh` records reusable patterns; `ph tick` deposits them into MemoryOS draft knowledge.",
        "",
        "## Stop / Escalate",
        "",
        "- Stop if the required evidence requires login, ToS, personal data, credentials, spend, or final submission.",
        "- Escalate if a ceiling claim has not been challenged by a different vendor/model.",
        "- Park if the contest rewards credentials or eligibility we cannot honestly satisfy.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--platform", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--archetype", default="", help="comma-separated explicit archetype keys")
    args = ap.parse_args()

    archetype_keys = detect_archetypes(args.name, args.platform, args.domain, args.archetype)
    rows = task_rows(archetype_keys)
    base = registry_campaign_dir(args.key) or CONTROL / "campaigns" / args.key
    base.mkdir(parents=True, exist_ok=True)

    data = {
        "key": args.key,
        "name": args.name,
        "platform": args.platform,
        "domain": args.domain,
        "url": args.url,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "archetypes": archetype_keys,
        "backlog": rows,
    }
    (base / "PRIZE_GAP_LOOP.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (base / "PRIZE_GAP_LOOP.md").write_text(
        md_for(args.key, args.name, args.platform, args.domain, args.url, archetype_keys, rows),
        encoding="utf-8",
    )

    print(base / "PRIZE_GAP_LOOP.md")
    print(base / "PRIZE_GAP_LOOP.json")
    print(f"archetypes={','.join(archetype_keys)} backlog={len(rows)}")


if __name__ == "__main__":
    main()
