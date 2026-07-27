#!/usr/bin/env python3
"""Build the next cross-domain competition pool for prizehunter.

Inputs are live/generated candidate TSVs plus manual seeds. Output is a compact
ranked pool with enough context to start RECON without rereading every source.
"""
import csv
import os
import re
from datetime import datetime


HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.abspath(os.path.join(HERE, ".."))
TODAY = datetime(2026, 6, 13)

CORRECTIONS = {
    "aic-09-aic-4": {
        "source": "culture",
        "url": "https://www.culture.go.kr/digicon",
        "kind": "build",
        "status": "open",
        "note": "Claude recon 2026-06-13: real portal is culture.go.kr/digicon, not aichallenge4all. 문체부 AI·데이터 활용 공모전, 6/26 deadline, 5천만원, culture-data product can feed 범정부 제14회.",
    },
    "2026-motie-public-data": {
        "source": "data.go.kr",
        "name": "제14회 범정부 공공데이터·AI 활용 창업경진대회",
        "url": "https://www.data.go.kr/suc/startup.do",
        "kind": "build",
        "deadline": "2026-09/TBA",
        "status": "prep",
        "note": "Claude recon 2026-06-13: original MOTIE/datacontest label was conflated. Target is 행안부/NIA 범정부 제14회; build reusable 공공데이터 product now, submit when 2026 window opens.",
    },
    "2026-busan-publicdata-ai-startup": {
        "deadline": "TBA",
        "status": "park",
        "note": "Claude recon 2026-06-13: no official 2026 Busan notice is open yet; park and reuse 범정부/aic public-data stack if/when announced.",
    },
    "2026-usaii-global-ai": {
        "deadline": "2026-06-06",
        "status": "kill",
        "note": "Claude recon 2026-06-13: registration closed 2026-06-06, qualifier passed, student-only, team-only. Kill for this cycle.",
    },
}


def read_tsv(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def classify(title):
    if re.search(r"독후감|문학|문예|에세이|글쓰기|시나리오|스토리", title):
        return "text"
    if re.search(r"디자인|웹툰|영상|영화|미디어|사진|캐릭터|창작|아트", title):
        return "media"
    if re.search(r"데이터|AI|인공지능|해커톤|SW|소프트|개발|공공기관|기상|국방", title, re.I):
        return "build"
    if re.search(r"아이디어|건축|창업|제안|기획", title):
        return "idea"
    return "other"


def krw_from_text(text):
    best = 0
    for n, unit in re.findall(r"([0-9][0-9,]*)\s*(억|천만|만)\s*원?", text):
        base = int(n.replace(",", ""))
        best = max(best, base * (100_000_000 if unit == "억" else 10_000_000 if unit == "천만" else 10_000))
    return best


def money_to_krw(text):
    raw = str(text or "")
    if not raw or raw.lower() in {"kudos", "knowledge", "nan"}:
        return 0
    krw = krw_from_text(raw)
    if krw:
        return krw
    m = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(usd|us\\$|\\$)", raw, re.I)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1350)
    m = re.search(r"\\$\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", raw)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1350)
    m = re.search(r"([0-9][0-9,]*(?:\\.[0-9]+)?)\\s*(eur|€)", raw, re.I)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1450)
    m = re.search(r"€\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", raw)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1450)
    m = re.search(r"₹\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", raw)
    if m:
        return int(float(m.group(1).replace(",", "")) * 16)
    return 0


def is_past_deadline(value):
    text = str(value or "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19 if " " in fmt else 10], fmt) < TODAY
        except ValueError:
            pass
    return False


def score(row):
    title = row["name"]
    kind = row.get("kind") or classify(title)
    prize = int(float(str(row.get("prize_krw") or row.get("prize") or 0).replace(",", "") or 0))
    if prize == 0:
        prize = krw_from_text(" ".join(row.values()))
    status = row.get("status", "")
    note = row.get("note", "")
    edge = str(row.get("we_have_edge", "")).lower() in {"yes", "true", "1"}
    if "종료" in note or status in {"closed", "kill"} or is_past_deadline(row.get("deadline", "")):
        return -1
    if status in {"park", "monitor"}:
        return 35
    if status == "closed_or_verify":
        return 35
    if status == "invite_only":
        return 45
    if status == "eligibility_check":
        base_penalty = 12
    else:
        base_penalty = 0
    if "경품" in note or kind == "lottery":
        return 5
    base = {
        "build": 85,
        "idea": 82,
        "text": 80,
        "media": 72,
        "vision": 76,
        "ml": 86,
        "other": 55,
        "robotics": 35,
    }.get(kind, 55)
    if prize >= 100_000_000:
        base += 12
    elif prize >= 50_000_000:
        base += 9
    elif prize >= 10_000_000:
        base += 5
    if edge:
        base += 8
    if "robot" in str(row.get("hardware_required", "")):
        base -= 35
    return max(0, min(100, base - base_penalty))


def creative_owner(kind, name):
    blob = f"{kind} {name}"
    if kind in {"media", "text", "idea", "vision", "art_culture"}:
        return "codex_creative_director"
    if classify(blob) in {"media", "text", "idea"} or re.search(r"문학|문예|독후감|스토리|웹툰|디자인|영상|아트|예술|건축|브랜드|캐릭터|창작", blob):
        return "codex_creative_director"
    return "codex_recon"


def normalize():
    out = []
    for r in read_tsv(os.path.join(CONTROL, "manual_competition_seeds.tsv")):
        out.append(
            {
                "source": r.get("platform", "manual"),
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "url": r.get("url", ""),
                "kind": r.get("kind", ""),
                "prize_krw": r.get("prize_krw", "0"),
                "deadline": r.get("deadline", "TBD"),
                "status": r.get("status", ""),
                "note": r.get("note", ""),
                "we_have_edge": "yes",
            }
        )
    for r in read_tsv(os.path.join(CONTROL, "candidates_contests.tsv")):
        out.append(
            {
                "source": r.get("platform", ""),
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "url": r.get("url", ""),
                "kind": classify(r.get("name", "")),
                "prize_krw": "0",
                "deadline": "TBD",
                "status": "",
                "note": "generic contest-platform candidate; fetch detail before commit",
                "we_have_edge": "yes" if classify(r.get("name", "")) in {"build", "idea", "text"} else "maybe",
            }
        )
    for idx, r in enumerate(read_tsv(os.path.join(CONTROL, "candidates_aic.tsv")), 1):
        aic_slug = re.sub(r"[^a-z0-9]+", "-", r.get("name", "").lower()).strip("-")
        out.append(
            {
                "source": "aichallenge4all",
                "id": f"aic-{idx:02d}-{aic_slug or 'competition'}",
                "name": r.get("name", ""),
                "url": "https://aichallenge4all.or.kr/competitions",
                "kind": r.get("domain", ""),
                "prize_krw": r.get("prize", "0"),
                "deadline": f"D-{r.get('days_to_deadline', '?')}",
                "status": "open",
                "note": r.get("note", ""),
                "we_have_edge": r.get("we_have_edge", ""),
                "hardware_required": r.get("hardware_required", ""),
            }
        )
    for r in read_tsv(os.path.join(CONTROL, "candidates_kaggle.tsv")):
        out.append(
            {
                "source": "kaggle",
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "url": r.get("url", ""),
                "kind": "ml",
                "prize_krw": str(money_to_krw(r.get("prize", ""))),
                "deadline": r.get("deadline", "TBD"),
                "status": "open" if not is_past_deadline(r.get("deadline", "")) else "closed",
                "note": f"{r.get('category','')} prize={r.get('prize','')}; Kaggle keyed adapter can submit programmatically when credentials are present.",
                "we_have_edge": "yes",
            }
        )
    for r in out:
        corr = CORRECTIONS.get(r.get("id", ""))
        if corr:
            r.update(corr)

    seen = {}
    for r in out:
        if not r["name"]:
            continue
        key = (r["source"], r["name"])
        if key not in seen or score(r) > score(seen[key]):
            seen[key] = r
    return sorted(seen.values(), key=score, reverse=True)


def main():
    rows = normalize()
    tsv = os.path.join(CONTROL, "NEXT_COMPETITION_POOL.tsv")
    md = os.path.join(CONTROL, "NEXT_COMPETITION_POOL.md")
    cols = ["score", "priority", "source", "kind", "creative_owner", "prize_krw", "deadline", "status", "id", "name", "url", "note"]
    with open(tsv, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            if score(r) < 50:
                continue
            enriched = {
                **r,
                "score": score(r),
                "priority": "P0" if score(r) >= 95 else "P1" if score(r) >= 85 else "P2",
                "creative_owner": creative_owner(r.get("kind", ""), r.get("name", "")),
            }
            f.write("\t".join(str(enriched.get(c, "")) for c in cols) + "\n")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Next Competition Pool\n\n")
        f.write("Policy: if the contest asks for 100%, prizehunter targets 120%+ quality: hidden-intent mining, our deficiency ledger, recon, reference mining, asset gathering, prototype/deck/package, visual QA, submission receipt, and learning receipt.\n\n")
        f.write("| score | prio | owner | source | kind | prize | deadline | competition |\n")
        f.write("|---:|---|---|---|---|---:|---|---|\n")
        for r in rows[:50]:
            if score(r) < 50:
                continue
            priority = "P0" if score(r) >= 95 else "P1" if score(r) >= 85 else "P2"
            owner = creative_owner(r.get("kind", ""), r.get("name", ""))
            f.write(f"| {score(r)} | {priority} | {owner} | {r.get('source','')} | {r.get('kind','')} | {r.get('prize_krw','0')} | {r.get('deadline','')} | [{r.get('name','')}]({r.get('url','')}) |\n")
        f.write("\n## System Gates\n\n")
        f.write("- DISCOVER: `ph discover` runs DACON, generic contest platforms, AIC, keyed Kaggle.\n")
        f.write("- TRIAGE: `NEXT_COMPETITION_POOL.tsv` ranks AI, data, design, writing, art, media, idea, hackathon targets together.\n")
        f.write("- GAP: `ph gap <key> \"<name>\"` generates judge needs, hidden intent, our deficiencies, and a 120%+ backlog by contest archetype.\n")
        f.write("- RECON: each committed target needs previous winners, organizer preferences, rules, scoring rubric, reference assets, and rights/AI-use constraints.\n")
        f.write("- BUILD: package must include the actual artifact, submission fields, visual/brand reference, deficiency-closure map, and evidence appendix.\n")
        f.write("- RECORD/LEARN: every decision and reusable pattern gets a receipt through `record_asset_receipt.sh` and `ph tick`.\n")
        f.write("- CREATIVE: design/media/literature/idea/art campaigns are Codex-led. Codex owns ideas, research, visual system, brand/character direction, references, and visual QA; Claude builds after Codex locks the creative brief.\n")
    print(md)
    print(tsv)
    print(f"pool={sum(1 for r in rows if score(r) >= 50)}")


if __name__ == "__main__":
    main()
