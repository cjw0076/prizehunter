#!/usr/bin/env python3
"""settle.py — '끝난 후' 스테이지 드라이버 (playbook/POSTERIOR.md).

watch : submitted/closed/lapsed 행을 OUTCOMES.tsv 에 등록(예측 스냅샷 포함),
        RESULTS_RADAR.md 렌더. tick 이 매 사이클 호출. 변경 없음이면 조용.
list  : 정산 대기(outcome=pending) 목록.
close : 결과 확정 원커맨드 —
        settle.py close <key> --outcome won|placed|lost|no_award|lapsed|withdrawn
                 [--placement "51/409"] [--prize 500000] [--evidence "..."] [--full]
        OUTCOMES 확정 → PRIZE_LEDGER 반영 → POSTMORTEM/CASE_STUDY 스켈레톤(수집데이터
        선기입; lapsed 는 간이 경로) → LESSONS stub → registry status→settled →
        memoryOS 예금 → PORTFOLIO_INDEX 재생성.

정직 강제: prize>0 이면 --evidence 필수. 예측 스냅샷은 등록 후 불변.
lapsed 정산은 '마감 유실' 기록이지 '미제출' 단정이 아니다.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

OUTCOMES = os.path.join(CT, "OUTCOMES.tsv")
RADAR = os.path.join(CT, "RESULTS_RADAR.md")
QUALITY = os.path.join(CT, "QUALITY_GATE_REPORT.tsv")
LEDGER = os.path.join(CT, "EXIT", "PRIZE_LEDGER.tsv")
LESSONS = os.path.join(CT, "results", "LESSONS.md")
REGISTRY = os.path.join(CT, "portfolio_registry.tsv")
RECEIPTS = os.path.join(CT, "receipts")

OCOLS = ["key", "lane", "first_seen", "expected_announce", "resolved_date",
         "predicted_win", "judge_quality", "outcome", "placement",
         "prize_won_krw", "evidence", "postmortem"]
TRACK = {"submitted", "closed", "lapsed", "settled"}
FINAL = {"won", "placed", "lost", "no_award", "lapsed", "withdrawn"}


def read_tsv(path, cols):
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#") or line.split("\t")[0] == cols[0]:
            continue
        parts = line.split("\t")
        rows.append(dict(zip(cols, parts + [""] * (len(cols) - len(parts)))))
    return rows


def write_outcomes(rows):
    tmp = OUTCOMES + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Outcomes ledger — 결과·교정의 원천 (playbook/POSTERIOR.md). 예측 스냅샷은 등록 후 불변.\n")
        f.write("\t".join(OCOLS) + "\n")
        for r in rows:
            f.write("\t".join((r.get(c, "") or "").replace("\t", " ") for c in OCOLS) + "\n")
    os.replace(tmp, OUTCOMES)


def quality_snapshot():
    q = {}
    for r in read_tsv(QUALITY, ["key", "lane", "status", "progress", "submission_readiness",
                                "judge_quality", "win_probability", "ev_stance",
                                "top_findings", "next_gate", "strategy_gaps"]):
        q[r["key"]] = r
    return q


def receipts_span(key):
    names = sorted(n for n in os.listdir(RECEIPTS) if key.lower() in n.lower()) if os.path.isdir(RECEIPTS) else []
    if not names:
        return "기록 0건"
    return f"기록 {len(names)}건 ({names[0][:8]} ~ {names[-1][:8]})"


def cmd_watch():
    today = datetime.now().strftime("%Y-%m-%d")
    reg = [r for r in P.parse_registry(with_extras=False) if r["status"] in TRACK]
    rows = read_tsv(OUTCOMES, OCOLS)
    known = {r["key"] for r in rows}
    q = quality_snapshot()
    added = 0
    for r in reg:
        if r["key"] in known:
            continue
        s = q.get(r["key"], {})
        rows.append({
            "key": r["key"], "lane": s.get("lane", ""), "first_seen": today,
            "expected_announce": "TBD", "resolved_date": "",
            "predicted_win": s.get("win_probability", ""),
            "judge_quality": s.get("judge_quality", ""),
            "outcome": "lapsed-pending" if r["status"] == "lapsed" else "pending",
            "placement": "", "prize_won_krw": "", "evidence": "", "postmortem": "",
        })
        added += 1
    if added:
        write_outcomes(rows)
    pending = [r for r in rows if r["outcome"].endswith("pending")]
    resolved = [r for r in rows if r["outcome"] in FINAL]
    L = [f"# Results Radar — {datetime.now():%Y-%m-%d %H:%M}", "",
         f"- 정산 대기 **{len(pending)}** · 확정 {len(resolved)} · (원장 OUTCOMES.tsv · 정산: `ph settle close <key> --outcome …`)",
         "", "## 정산 대기 (오래된 순 — 결과 발표 확인 필요, 포털 로그인은 founder gate)", "",
         "| key | 등록 | 예측win% | 상태 | 발표예정 |", "|---|---|---:|---|---|"]
    for r in sorted(pending, key=lambda x: x["first_seen"]):
        L.append(f"| {r['key']} | {r['first_seen']} | {r['predicted_win'] or '-'} | {r['outcome']} | {r['expected_announce']} |")
    if resolved:
        L += ["", "## 확정", "", "| key | outcome | placement | prize | evidence |", "|---|---|---|---:|---|"]
        for r in resolved:
            L.append(f"| {r['key']} | {r['outcome']} | {r['placement'] or '-'} | {r['prize_won_krw'] or '-'} | {(r['evidence'] or '-')[:70]} |")
    L += ["", "> 규칙: 확정 실현 수상만 승리 (results/RESULTS_LEDGER.md 와 동일). 예측 스냅샷은 불변.", ""]
    tmp = RADAR + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, RADAR)
    print(f"settle watch: outcomes+{added} pending={len(pending)} resolved={len(resolved)} → RESULTS_RADAR.md")


def set_registry_settled(key):
    lines = []
    hit = False
    for line in open(REGISTRY, encoding="utf-8"):
        raw = line.rstrip("\n")
        parts = raw.split("\t")
        if not raw.startswith("#") and len(parts) >= 11 and parts[0] == key:
            parts[8] = "settled"
            raw = "\t".join(parts)
            hit = True
        lines.append(raw)
    if hit:
        tmp = REGISTRY + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, REGISTRY)
    return hit


def update_prize_ledger(key, a, today):
    lcols = ["key", "competition", "deadline", "entered", "placement", "prize_pool",
             "won_amount", "status", "evidence"]
    if not os.path.exists(LEDGER):
        return
    comments = [l.rstrip("\n") for l in open(LEDGER, encoding="utf-8") if l.startswith("#")]
    rows = read_tsv(LEDGER, lcols)
    for r in rows:
        if r["key"] != key:
            continue
        if a.placement:
            r["placement"] = a.placement
        r["won_amount"] = str(a.prize) if a.prize else ("0" if a.outcome in ("lost", "no_award") else r["won_amount"] or "TBD")
        r["status"] = "settled"
        if a.evidence:
            r["evidence"] = a.evidence
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(comments) + ("\n" if comments else ""))
        f.write("\t".join(lcols) + "\n")
        for r in rows:
            f.write("\t".join((r.get(c, "") or "").replace("\t", " ") for c in lcols) + "\n")
    os.replace(tmp, LEDGER)


def postmortem_skeleton(key, reg_row, orow, a, today):
    d = os.path.join(CT, "campaigns", key)
    rr = reg_row or {}
    if rr.get("dir"):
        cand = os.path.join(os.path.abspath(os.path.join(CT, "..", "..")), rr["dir"])
        if os.path.isdir(cand):
            d = cand
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"POSTMORTEM_{key}.md")
    if os.path.exists(path):
        return path  # never clobber an existing postmortem
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""# 포스트모템 — {key} ({today})

> 자동 수집분은 선기입됨. **귀인·교훈은 세션/founder가 채운다** (playbook/POSTMORTEM.md 절차).

- 결과: **{a.outcome}** · placement {a.placement or 'TBD'} · prize {a.prize or 'TBD'} (증거: {a.evidence or 'TBD'})
- 예측 vs 실제: 등록시점 win% **{orow.get('predicted_win') or '?'}** / judge {orow.get('judge_quality') or '?'} → 실제 {a.outcome}
- 활동 타임라인: {receipts_span(key)}
- 최종 registry 상태: {rr.get('status', '?')} · progress {rr.get('progress', '?')} · best {rr.get('best', '-')}
- 축 가중치 (사후 확인): LB% / 논문% / peer% / 데모% — TBD
- public→private / 우승작 대비: TBD
- 잘된 점 (수상 시 — 레버 + 재현성): TBD
- 부족한 점 (탈락 시 — 바인딩 제약, 안전한 자책 금지): TBD
- cross-model 검증 (다른 모델 반박): TBD
- 추출 교훈 → results/LESSONS.md 1줄 + 적용법: TBD
- 다음 적용: TBD
""")
    return path


def case_study_skeleton(key, orow, a, today, pm_path):
    d = os.path.dirname(pm_path)
    path = os.path.join(d, f"CASE_STUDY_{key}.md")
    if os.path.exists(path):
        return path
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""# Case Study — {key}

> 인간 독자용(심사자·채용·바이어). 폴리시드 문장으로 채울 것 — §3.5 원칙: 제출물/포트폴리오는 인간 감성.

- **한 줄 결과**: {a.outcome} · {a.placement or ''} {('· ₩'+str(a.prize)) if a.prize else ''}
- **문제**: (대회가 푼 문제, 왜 어려운가)
- **접근 — 핵심 레버**: (무엇이 승부수였나 1-2개)
- **결과 (정량 + 증거)**: {a.evidence or 'TBD'}
- **배운 것**: (포스트모템 교훈 1-3줄)
- **재사용 자산**: (코드/기법/프롬프트 — 다음 대회로 이월되는 것)
""")
    return path


def cmd_close(a):
    today = datetime.now().strftime("%Y-%m-%d")
    if a.prize and a.prize > 0 and not a.evidence:
        sys.exit("REFUSED: prize>0 은 --evidence 필수 (확정만 승리 — playbook/POSTERIOR.md §3)")
    rows = read_tsv(OUTCOMES, OCOLS)
    orow = next((r for r in rows if r["key"] == a.key), None)
    if orow is None:
        orow = {c: "" for c in OCOLS}
        orow.update({"key": a.key, "first_seen": today, "expected_announce": "TBD"})
        rows.append(orow)
    orow.update({"resolved_date": today, "outcome": a.outcome,
                 "placement": a.placement or orow.get("placement", ""),
                 "prize_won_krw": str(a.prize) if a.prize else orow.get("prize_won_krw", ""),
                 "evidence": a.evidence or orow.get("evidence", "")})
    reg_row = next((r for r in P.parse_registry(with_extras=False) if r["key"] == a.key), None)
    pm_path = ""
    if a.outcome != "lapsed" or a.full:
        pm_path = postmortem_skeleton(a.key, reg_row, orow, a, today)
        cs_path = case_study_skeleton(a.key, orow, a, today, pm_path)
        orow["postmortem"] = os.path.relpath(pm_path, CT)
        if os.path.exists(LESSONS):
            with open(LESSONS, "a", encoding="utf-8") as f:
                f.write(f"- [{a.key}] {a.outcome} ({a.placement or '-'}) — 교훈: TBD ← {os.path.relpath(pm_path, CT)} 채운 뒤 여기 1줄로. ({today})\n")
        # flywheel: deposit the postmortem as draft memory (best-effort)
        subprocess.run(["bash", os.path.join(HERE, "memoryos_bridge.sh"), "deposit", pm_path],
                       capture_output=True, timeout=200)
        print(f"postmortem: {pm_path}\ncase study: {cs_path}")
    write_outcomes(rows)
    update_prize_ledger(a.key, a, today)
    if set_registry_settled(a.key):
        print(f"registry: {a.key} → settled")
    subprocess.run([sys.executable, os.path.join(HERE, "build_portfolio.py")], capture_output=True, timeout=60)
    cmd_watch()
    print(f"settled: {a.key} outcome={a.outcome}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("watch")
    sub.add_parser("list")
    c = sub.add_parser("close")
    c.add_argument("key")
    c.add_argument("--outcome", required=True, choices=sorted(FINAL))
    c.add_argument("--placement", default="")
    c.add_argument("--prize", type=int, default=0)
    c.add_argument("--evidence", default="")
    c.add_argument("--full", action="store_true", help="lapsed 에도 풀 포스트모템 생성")
    a = ap.parse_args()
    if a.cmd == "close":
        cmd_close(a)
    elif a.cmd == "list":
        for r in read_tsv(OUTCOMES, OCOLS):
            if r["outcome"].endswith("pending"):
                print(f"{r['key']:36} since {r['first_seen']}  predicted_win={r['predicted_win'] or '-'}")
    else:
        cmd_watch()


if __name__ == "__main__":
    main()
