#!/usr/bin/env python3
"""deadline_watchdog.py — 마감 감시 + 경과 자동 아카이브 + 임박 배치 알림.

세션이 떠 있을 때만 마감이 보이던 구멍(pm_tick 은 cron 미등록)을 막는
cron-side 안전망. portfolio_tick.sh 이 3시간마다 호출한다:

 1. registry 전 행의 마감(dday)을 파싱해 DEADLINE_RADAR.md 갱신
 2. 마감이 GRACE(2일) 이상 지난 active-계열 행을 status=lapsed 로 자동 아카이브.
    단, 과거 날짜가 '마감 문맥'(마감/접수/제출/due…) 옆에 있을 때만 — 작업일자·
    발표일을 마감으로 오인해 전환하지 않는다. lapsed = "마감 경과 + 이 저장소에
    제출증거 미기록"이며 '제출 안 함'의 단정이 아니다 — founder 가 외부에서
    제출했다면 registry 를 정정하면 된다.
    모든 전환은 LAPSED_LEDGER.tsv 에 append-only 기록 (no record destroyed).
 3. 신규 lapse 또는 D≤3 임박 행이 있으면 tools/tg.sh 로 하루 최대 1회 배치 푸시
    (MONITORING alert policy: 완료/결정필요 게이트만, 루틴 진행상황 금지).

usage: deadline_watchdog.py [--dry-run|--report]
  --dry-run  변경/알림 없이 계획만 출력
  --report   radar 재생성+출력만 (registry 불변, 알림 없음) — `ph radar` 용
"""
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CT)
import prizehunter_ui as P  # noqa: E402  (extract_deadline/parse_registry 재사용)

REGISTRY = os.path.join(CT, "portfolio_registry.tsv")
RADAR = os.path.join(CT, "DEADLINE_RADAR.md")
LEDGER = os.path.join(CT, "LAPSED_LEDGER.tsv")
STATE = os.path.join(CT, ".runs", "deadline_watchdog.state")
TG = os.path.join(HERE, "tg.sh")

LAPSE_STATUSES = {"active", "blocked", "scaffold", "polishing", "recon", "ready-gate"}
GRACE_DAYS = 2  # dday <= -2 에서만 자동 전환 (날짜 파싱 오차·심사/발표일 혼동 보호)
NCOLS = 11
S_I, B_I = 8, 9  # status / blocker 컬럼 인덱스

# 과거 날짜를 '마감'으로 믿는 조건: 날짜 주변(앞 30자/뒤 15자)에 마감 문맥 키워드.
# 작업일자("2026-07-02 self-heal로 등록")나 발표일을 마감으로 오인하지 않기 위한 가드.
DATE_PATS = [
    r"\b20\d{2}[-./]\d{1,2}[-./]\d{1,2}(?:\s+\d{1,2}:\d{2})?\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b",
    r"(?:20\d{2}년\s*)?\d{1,2}월\s*\d{1,2}일",
    r"\b\d{1,2}/\d{1,2}\b",
]
DL_KEY = re.compile(r"마감|접수|제출|응모|due|deadline|closes?|until|till|까지|upload|submit", re.I)


def clip(t, n=160):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def deadline_confirmed(r):
    text = " ".join((r.get("blocker") or "", r.get("next_lever") or ""))
    for pat in DATE_PATS:
        for m in re.finditer(pat, text, re.I):
            ctx = text[max(0, m.start() - 30): m.end() + 15]
            if DL_KEY.search(ctx):
                return True
    return False


def lapse_candidates(rows):
    cand, ambiguous = [], []
    for r in rows:
        if r["status"] not in LAPSE_STATUSES or r.get("dday") is None or r["dday"] > -GRACE_DAYS:
            continue
        (cand if deadline_confirmed(r) else ambiguous).append(r)
    return cand, ambiguous


def rewrite_registry(cand, today):
    info = {r["key"]: r for r in cand}
    lines, changed = [], []
    with open(REGISTRY, encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            parts = raw.split("\t")
            if raw.startswith("#") or len(parts) < NCOLS or parts[0] not in info:
                lines.append(raw)
                continue
            r = info[parts[0]]
            old_status, old_blocker = parts[S_I], parts[B_I]
            parts[S_I] = "lapsed"
            parts[B_I] = (f"[LAPSED {today} auto: 마감 {r['deadline']} 경과, 제출증거 미기록 — "
                          f"실제 제출했다면 registry 정정] {old_blocker}")
            changed.append((r["key"], r["deadline"], old_status, old_blocker))
            lines.append("\t".join(parts))
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, REGISTRY)
    if changed:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", encoding="utf-8") as f:
            if new:
                f.write("# Lapsed Ledger — deadline_watchdog 자동 아카이브 전환의 append-only 기록.\n")
                f.write("# lapsed ≠ '제출 안 함' 단정. 외부 제출이 확인되면 registry 를 정정하고 이 행은 남긴다.\n")
                f.write("date\tkey\tdeadline\told_status\told_blocker\n")
            for key, dl, st, bl in changed:
                f.write(f"{today}\t{key}\t{dl}\t{st}\t{clip(bl, 240)}\n")
    return changed


def write_radar(rows, changed, ambiguous, today, now):
    up = sorted((r for r in rows
                 if r["status"] in LAPSE_STATUSES and r.get("dday") is not None and r["dday"] >= 0),
                key=lambda r: r["dday"])
    just = [r for r in rows
            if r["status"] in LAPSE_STATUSES and r.get("dday") is not None
            and -GRACE_DAYS < r["dday"] < 0]
    lapsed_total = sum(1 for r in rows if r["status"] == "lapsed")
    L = [f"# Deadline Radar — {now}", "",
         f"- watchdog: 마감경과 {GRACE_DAYS}일 유예+마감문맥 확인 후 자동 lapsed · D≤3/lapse 배치 알림(하루≤1회) · 원장 LAPSED_LEDGER.tsv",
         f"- 누적 lapsed: {lapsed_total} · 오늘 전환: {len(changed)}", "",
         "## ⏰ 임박 (D≤14, active-계열)", "",
         "| D- | key | status | gate | deadline | blocker |",
         "|---:|---|---|---|---|---|"]
    for r in (r for r in up if r["dday"] <= 14):
        gate = "🔴founder" if r["founder_gate"] else ""
        L.append(f"| {r['dday']} | {r['key']} | {r['status']} | {gate} | {r['deadline']} | {clip(r['blocker'], 90)} |")
    L += ["", "## 📆 그 외 다가오는 마감", ""]
    for r in (r for r in up if r["dday"] > 14):
        L.append(f"- D-{r['dday']} {r['key']} ({r['deadline']})")
    if just:
        L += ["", f"## 🟡 방금 지남 (유예 {GRACE_DAYS}일 내) — 확인 필요", ""]
        L += [f"- {r['key']} — 마감 {r['deadline']} (D{r['dday']}) · {clip(r['blocker'], 90)}" for r in just]
    if ambiguous:
        L += ["", "## 🔍 날짜 모호 (과거 날짜만 감지, 마감 문맥 없음 — 마감일 기입 필요)", ""]
        L += [f"- {r['key']} — 감지된 날짜 {r['deadline']} (D{r['dday']}) · {clip(r['blocker'], 90)}" for r in ambiguous]
    if changed:
        L += ["", "## ⚰️ 오늘 자동 lapsed", ""]
        L += [f"- {k} — 마감 {dl} (was {st})" for k, dl, st, _ in changed]
    L += ["", "> lapsed = '마감 경과 + 여기 증거 미기록'. '제출 안 함'의 단정이 아니다 — 외부 제출 확인 시 registry 정정.", ""]
    tmp = RADAR + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, RADAR)
    return up, just


def maybe_push(up, changed, today):
    urgent = [r for r in up if r["dday"] <= 3]
    if not urgent and not changed:
        return "no-alert"
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    if st.get("last_push") == today:
        return "already-pushed-today"
    msg = [f"📅 Deadline radar {today}"]
    if urgent:
        msg.append("⏰ " + " · ".join(
            f"D-{r['dday']} {r['key']}{'(🔴gate)' if r['founder_gate'] else ''}" for r in urgent[:6]))
    if changed:
        msg.append("⚰️ auto-lapsed: " + ", ".join(k for k, *_ in changed[:10])
                   + " — 실제 제출했으면 registry 정정")
    msg.append("→ ph radar")
    try:
        r = subprocess.run(["bash", TG, "\n".join(msg)], capture_output=True, text=True, timeout=25)
        ok = "tg send: 200" in (r.stdout + r.stderr)
    except Exception:
        ok = False
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump({"last_push": today if ok else st.get("last_push", ""), "last_try": today}, f)
    return "pushed" if ok else "push-failed(tg)"


def main():
    dry = "--dry-run" in sys.argv
    report = "--report" in sys.argv
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = P.parse_registry(with_extras=False)
    cand, ambiguous = lapse_candidates(rows)
    if dry:
        print(f"deadline_watchdog DRY-RUN — lapse 후보 {len(cand)} (마감문맥 확인됨):")
        for r in cand:
            print(f"  {r['key']:36} dday={r['dday']:<5} deadline={r['deadline']} status={r['status']}")
        print(f"날짜모호(전환 제외) {len(ambiguous)}:")
        for r in ambiguous:
            print(f"  {r['key']:36} dday={r['dday']:<5} deadline={r['deadline']} status={r['status']}")
        up = sorted((r for r in rows if r["status"] in LAPSE_STATUSES
                     and r.get("dday") is not None and 0 <= r["dday"] <= 14),
                    key=lambda r: r["dday"])
        print(f"임박 D≤14 — {len(up)}:")
        for r in up:
            print(f"  D-{r['dday']:<3} {r['key']:36} {r['status']}")
        return
    changed = []
    if not report and cand:
        changed = rewrite_registry(cand, today)
        rows = P.parse_registry(with_extras=False)
        _, ambiguous = lapse_candidates(rows)
    up, just = write_radar(rows, changed, ambiguous, today, now)
    alert = "skipped(report)" if report else maybe_push(up, changed, today)
    print(f"deadline_watchdog: lapsed+{len(changed)} upcoming14={sum(1 for r in up if r['dday'] <= 14)} "
          f"just_missed={len(just)} ambiguous={len(ambiguous)} alert={alert} → DEADLINE_RADAR.md")
    if report:
        print()
        print(open(RADAR, encoding="utf-8").read())


if __name__ == "__main__":
    main()
