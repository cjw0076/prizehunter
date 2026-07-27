#!/usr/bin/env python3
"""pnl_sync.py — registry ↔ EXIT/PRIZE_LEDGER.tsv 자동 동기화 + P&L 요약.

PRIZE_LEDGER 머리말의 HONESTY RULE 을 그대로 상속한다:
  - 사람이 채운 placement / prize_pool / won_amount / evidence 는 절대 덮지 않는다
  - 모르는 값은 TBD — 지어내지 않는다
자동으로 정렬하는 것만:
  ① 커버리지 — registry 의 모든 대회가 원장에 행으로 존재
  ② status 컬럼 — registry 가 진실원천 (원장이 registry 와 모순되던 문제 제거)
  ③ 비어있는(TBD) deadline 채움
비용 측은 EXIT/COSTS.tsv (append-only 기입) 합산 → EXIT/PNL_SUMMARY.md 요약.
portfolio_tick.sh 이 3시간마다 호출하므로 원장은 더 이상 얼지 않는다.
"""
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

LEDGER = os.path.join(CT, "EXIT", "PRIZE_LEDGER.tsv")
COSTS = os.path.join(CT, "EXIT", "COSTS.tsv")
SUMMARY = os.path.join(CT, "EXIT", "PNL_SUMMARY.md")

LCOLS = ["key", "competition", "deadline", "entered", "placement",
         "prize_pool", "won_amount", "status", "evidence"]

ENTERED = {"submitted": "yes"}
for _s in ("active", "blocked", "scaffold", "recon", "polishing", "ready-gate"):
    ENTERED[_s] = "in_progress"
# closed/lapsed/hold/ceiling → TBD: 제출 여부를 상태만으로 단정하지 않는다


def num(v):
    try:
        return float(re.sub(r"[,₩\s원]", "", v or ""))
    except Exception:
        return None


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    reg = {r["key"]: r for r in P.parse_registry(with_extras=False)}

    comments, rows = [], []
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding="utf-8"):
            line = line.rstrip("\n")
            if line.startswith("#"):
                comments.append(line)
                continue
            if not line.strip():
                continue
            parts = line.split("\t")
            if parts[0] == "key":
                continue
            rows.append(dict(zip(LCOLS, parts + [""] * (len(LCOLS) - len(parts)))))
    known = {r["key"] for r in rows}

    synced = 0
    for r in rows:
        k = r["key"]
        if k not in reg:
            continue
        if r.get("status") != reg[k]["status"]:
            r["status"] = reg[k]["status"]
            synced += 1
        # registry says submitted → entered=yes is derivation, not fabrication
        # (the evidence audit in submission_board polices the submitted claim itself)
        if ENTERED.get(reg[k]["status"]) == "yes" and r.get("entered") != "yes":
            r["entered"] = "yes"
            synced += 1
        if r.get("deadline") in ("", "TBD") and reg[k].get("deadline"):
            r["deadline"] = reg[k]["deadline"]
            synced += 1

    added = 0
    for k, rr in reg.items():
        if k in known:
            continue
        rows.append({
            "key": k, "competition": k,
            "deadline": rr.get("deadline") or "TBD",
            "entered": ENTERED.get(rr["status"], "TBD"),
            "placement": "TBD", "prize_pool": "TBD", "won_amount": "TBD",
            "status": rr["status"],
            "evidence": f"VERIFY: auto-added {today} from registry — fill placement/prize/result",
        })
        added += 1

    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if comments:
            f.write("\n".join(comments) + "\n")
        f.write("\t".join(LCOLS) + "\n")
        for r in rows:
            f.write("\t".join((r.get(c, "") or "").replace("\t", " ") for c in LCOLS) + "\n")
    os.replace(tmp, LEDGER)

    if not os.path.exists(COSTS):
        with open(COSTS, "w", encoding="utf-8") as f:
            f.write("# Cost Ledger — 운영비의 append-only 기록 (P&L 비용 측; PRIZE_LEDGER 와 같은 HONESTY RULE).\n")
            f.write("# key = registry key 또는 'infra'(공통). item 예: api-credit, subscription, gpu, 응모료.\n")
            f.write("date\tkey\titem\tamount_krw\tevidence\n")

    cost_total, cost_n = 0.0, 0
    for line in open(COSTS, encoding="utf-8"):
        if line.startswith("#") or line.startswith("date") or not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        v = num(parts[3]) if len(parts) > 3 else None
        if v is not None:
            cost_total += v
            cost_n += 1

    won_numeric = [(r["key"], num(r["won_amount"])) for r in rows]
    won_numeric = [(k, v) for k, v in won_numeric if v is not None and v > 0]
    won_total = sum(v for _, v in won_numeric)
    tbd_won = sum(1 for r in rows if (r.get("won_amount") or "TBD") == "TBD")
    entered_yes = sum(1 for r in rows if r.get("entered") == "yes")
    in_prog = sum(1 for r in rows if r.get("entered") == "in_progress")
    verify_q = [r for r in rows
                if r.get("status") in ("submitted", "closed") and (r.get("placement") or "TBD") == "TBD"]

    with open(SUMMARY + ".tmp", "w", encoding="utf-8") as o:
        o.write(f"# P&L Summary — {datetime.now():%Y-%m-%d %H:%M}\n\n")
        o.write("원칙: 기록값만 합산한다. TBD 는 0 으로 세지 않고 TBD 로 보고한다 (no-launder 양방향).\n\n")
        o.write(f"- coverage: ledger **{len(rows)}** rows (registry {len(reg)} 전체 포함 · 이번 sync: {synced}건 정렬, {added}행 추가)\n")
        o.write(f"- entered: yes **{entered_yes}** · in_progress {in_prog}\n")
        o.write(f"- 상금 확정 수령: **₩{won_total:,.0f}** ({len(won_numeric)}건) · won=TBD {tbd_won}건\n")
        o.write(f"- 비용 기록: **₩{cost_total:,.0f}** ({cost_n}건, EXIT/COSTS.tsv — API크레딧/구독은 기입해야 잡힌다)\n")
        o.write(f"- net (기록 기준): **₩{won_total - cost_total:,.0f}** — TBD 다수인 동안은 하한선으로만 읽는다\n\n")
        if won_numeric:
            o.write("## 확정 수령\n\n")
            o.write("\n".join(f"- {k}: ₩{v:,.0f}" for k, v in won_numeric) + "\n\n")
        o.write("## 결과 확인 대기 (submitted/closed 인데 placement TBD)\n\n")
        for r in verify_q[:15]:
            o.write(f"- {r['key']} — {(r.get('evidence') or '')[:110]}\n")
        if not verify_q:
            o.write("- 없음\n")
    os.replace(SUMMARY + ".tmp", SUMMARY)
    print(f"pnl_sync: rows={len(rows)} added={added} synced={synced} "
          f"won=₩{won_total:,.0f} costs=₩{cost_total:,.0f} → EXIT/PNL_SUMMARY.md")


if __name__ == "__main__":
    main()
