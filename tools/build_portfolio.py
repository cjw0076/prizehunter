#!/usr/bin/env python3
"""build_portfolio.py — OUTCOMES.tsv + 케이스스터디 → PORTFOLIO_INDEX.md.

founder 실적 포트폴리오 · EXIT 매각 증빙 · 인플루언서 콘텐츠의 공통 소스.
규칙: results/RESULTS_LEDGER.md 와 동일 — **확정 실현 수상만 승리** (no-launder).
"""
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
OUTCOMES = os.path.join(CT, "OUTCOMES.tsv")
OUT = os.path.join(CT, "PORTFOLIO_INDEX.md")
OCOLS = ["key", "lane", "first_seen", "expected_announce", "resolved_date",
         "predicted_win", "judge_quality", "outcome", "placement",
         "prize_won_krw", "evidence", "postmortem"]
ORDER = {"won": 0, "placed": 1, "no_award": 2, "lost": 3, "withdrawn": 4, "lapsed": 5}


def rows():
    out = []
    if not os.path.exists(OUTCOMES):
        return out
    for line in open(OUTCOMES, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#") or line.startswith("key\t"):
            continue
        parts = line.split("\t")
        out.append(dict(zip(OCOLS, parts + [""] * (len(OCOLS) - len(parts)))))
    return out


def find_case_study(key):
    for base in (os.path.join(CT, "campaigns", key),):
        p = os.path.join(base, f"CASE_STUDY_{key}.md")
        if os.path.exists(p):
            return os.path.relpath(p, CT)
    return ""


def main():
    rs = rows()
    resolved = sorted((r for r in rs if r["outcome"] in ORDER),
                      key=lambda r: (ORDER[r["outcome"]], r["key"]))
    pending = [r for r in rs if r["outcome"].endswith("pending")]
    wins = [r for r in resolved if r["outcome"] in ("won", "placed") and (r["prize_won_krw"] or "").replace("TBD", "")]
    total_won = sum(int(r["prize_won_krw"]) for r in resolved
                    if (r["prize_won_krw"] or "").isdigit())
    L = [f"# Portfolio Index — 대회 성과 (자동 생성 {datetime.now():%Y-%m-%d %H:%M})", "",
         "> 규칙: **확정 실현 수상만 승리** (수동 정직 점수판: results/RESULTS_LEDGER.md · 절차: playbook/POSTERIOR.md).",
         "> 케이스스터디는 인간 독자용 — 심사자/채용/바이어가 읽는 폴리시드 산출물.", "",
         f"- 추적 대회 **{len(rs)}** · 확정 결과 {len(resolved)} · 결과 대기 {len(pending)} · 확정 상금 **₩{total_won:,}**", "",
         "## 확정 결과", "",
         "| key | outcome | placement | prize | case study | postmortem | evidence |",
         "|---|---|---|---:|---|---|---|"]
    for r in resolved:
        cs = find_case_study(r["key"])
        L.append("| {k} | {o} | {p} | {pr} | {cs} | {pm} | {ev} |".format(
            k=r["key"], o=r["outcome"], p=r["placement"] or "-",
            pr=r["prize_won_krw"] or "-",
            cs=f"[✓]({cs})" if cs else "-",
            pm=f"[✓]({r['postmortem']})" if r["postmortem"] else "-",
            ev=(r["evidence"] or "-")[:60]))
    if not resolved:
        L.append("| — | 아직 확정 결과 없음 | | | | | |")
    L += ["", "## 결과 대기", "",
          ", ".join(r["key"] for r in pending) or "없음", "",
          "> 갱신: `ph settle close <key> --outcome … --evidence …` → 이 인덱스 자동 재생성.", ""]
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, OUT)
    print(f"portfolio: resolved={len(resolved)} pending={len(pending)} won=₩{total_won:,} → PORTFOLIO_INDEX.md")


if __name__ == "__main__":
    main()
