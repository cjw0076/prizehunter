#!/usr/bin/env python3
"""influence_tick.py — §3.5 인플루언서 파이프라인의 '가동' 레이어.

빌드만 되고 한 번도 흐르지 않던 콘텐츠를 이벤트-드리븐으로 흐르게 한다:
  · 이벤트(매 tick): 신규 submitted → '도전' 초안 / OUTCOMES 신규 won|placed → '성과' 초안
  · --weekly: 보드 요약 다이제스트 초안
산출물은 campaigns/influencer/drafts/*.md + POSTING_QUEUE.md **초안 큐까지만** —
외부 게시는 founder gate (§4). 3대 기둥 톤: ①AI가 혼자 ②숫자가 올라간다 ③시스템 공개.
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402

DRAFTS = os.path.join(CT, "campaigns", "influencer", "drafts")
QUEUE = os.path.join(CT, "campaigns", "influencer", "POSTING_QUEUE.md")
STATE = os.path.join(CT, ".runs", "influence.state")
OUTCOMES = os.path.join(CT, "OUTCOMES.tsv")


def outcomes():
    rows = []
    if not os.path.exists(OUTCOMES):
        return rows
    hdr = None
    for line in open(OUTCOMES, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if hdr is None:
            hdr = parts
            continue
        rows.append(dict(zip(hdr, parts + [""] * (len(hdr) - len(parts)))))
    return rows


def write_draft(slug, title, body):
    os.makedirs(DRAFTS, exist_ok=True)
    path = os.path.join(DRAFTS, f"{datetime.now():%Y%m%d}_{slug}.md")
    if os.path.exists(path):
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n> 초안 — founder 승인 후 게시 (외부 게시=founder gate). 톤: 이상함+노력 가시화.\n\n{body}\n")
    with open(QUEUE, "a", encoding="utf-8") as f:
        f.write(f"- [ ] {datetime.now():%Y-%m-%d} `{os.path.basename(path)}` — {title}\n")
    return path


def main():
    weekly = "--weekly" in sys.argv
    st = {"submitted": [], "resolved": []}
    first_run = not os.path.exists(STATE)
    try:
        st.update(json.load(open(STATE)))
    except Exception:
        pass
    made = []
    rows = P.parse_registry(with_extras=False)
    if first_run:
        # seed only — past submissions are old news; drafting "오늘 제출했다" for them would be false
        st["submitted"] = [r["key"] for r in rows if r["status"] == "submitted"]
        st["resolved"] = [o["key"] for o in outcomes() if o["outcome"] in ("won", "placed")]
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(st, open(STATE, "w"))
        print(f"influence: state seeded ({len(st['submitted'])} submitted, {len(st['resolved'])} resolved) — drafts start from next event")
        return
    for r in rows:
        if r["status"] == "submitted" and r["key"] not in st["submitted"]:
            p = write_draft(f"submit_{r['key']}", f"AI가 혼자 제출했다 — {r['key']}",
                            f"오늘도 AI가 사람 없이 대회 하나를 제출까지 끌고 갔다.\n\n"
                            f"- 대회: {r['key']}\n- 상태: 제출 완료, 결과 대기\n"
                            f"- 시스템: discover→build→submit 자동 루프의 {sum(1 for x in rows if x['status']=='submitted')}번째 제출\n\n"
                            f"(플랫폼별 변형: campaigns/influencer/platform_poster.py TEMPLATES 참조)")
            st["submitted"].append(r["key"])
            if p:
                made.append(p)
    for o in outcomes():
        if o["outcome"] in ("won", "placed") and o["key"] not in st["resolved"]:
            p = write_draft(f"result_{o['key']}", f"결과가 나왔다 — {o['key']}: {o['outcome']} {o['placement']}",
                            f"AI가 혼자 나간 대회의 결과.\n\n- {o['key']}: **{o['outcome']}** ({o['placement']})"
                            f"{' · ₩' + o['prize_won_krw'] if o['prize_won_krw'].isdigit() else ''}\n"
                            f"- 증거: {o['evidence'][:80]}\n- 예측 win% {o['predicted_win'] or '?'} → 실제 {o['outcome']}\n")
            st["resolved"].append(o["key"])
            if p:
                made.append(p)
    if weekly:
        s = P.summary(rows)
        p = write_draft("weekly_digest", f"주간 리포트 — 대회 {s['total']}개를 굴리는 AI",
                        f"- 전체 {s['total']} · submitted {s['submitted']} · active {s['active']} · founder 게이트 {s['founder_gates']}\n"
                        f"- 이번 주 하이라이트: (수동 큐레이션 — PORTFOLIO_INDEX.md / DEADLINE_RADAR.md 참조)\n")
        if p:
            made.append(p)
    json.dump(st, open(STATE, "w"))
    print(f"influence: drafts+{len(made)} queue={QUEUE if made else 'no-change'}")


if __name__ == "__main__":
    main()
