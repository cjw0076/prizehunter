#!/usr/bin/env python3
"""result_check.py — 공개 페이지로 대회 결과를 자동 확인 (settle 반자동화).

founder 지시(2026-07-11): 결과 확인을 founder-gate 로 방치하지 말 것 — 공개 페이지는
curl/playwright 로 직접 본다. 로그인 필요한 곳만 vault 자격증명/founder 로 넘긴다.

어댑터:
  devpost  : ① 해커톤 홈 "Winners announced" 배너 ② 프로젝트 페이지(서버렌더)의
             "Winner" 리본 유무 — 리본 없음 + 발표됨 = lost 근거.
  keyword  : 임의 공지 URL 에서 키워드(발표|수상|선정|winner) 존재 확인만 (판정은 사람).
설정: RESULT_SOURCES.tsv (key, adapter, url, project_url, note)
출력: RESULT_CHECK.md + `ph settle close …` 제안 라인. tick 이 일 1회 호출.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, date

HERE = os.path.dirname(os.path.abspath(__file__))
CT = os.path.abspath(os.path.join(HERE, ".."))
SOURCES = os.path.join(CT, "RESULT_SOURCES.tsv")
OUT = os.path.join(CT, "RESULT_CHECK.md")
STATE = os.path.join(CT, ".runs", "result_check.stamp")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def fetch(url, timeout=25):
    try:
        r = subprocess.run(["curl", "-sL", "-A", UA, "--max-time", str(timeout), url],
                           capture_output=True, text=True, timeout=timeout + 10)
        return r.stdout or ""
    except Exception:
        return ""


def devpost(url, project_url):
    home = fetch(url)
    announced = bool(re.search(r"winners announced", home, re.I))
    verdict, detail = "pending", f"announced={announced}"
    if project_url:
        proj = fetch(project_url)
        # 서버렌더 실콘텐츠인지 확인(제목/본문 존재) — 빈 셸이면 판정 보류
        real = len(proj) > 20000 and "devpost" in proj.lower()
        won = bool(re.search(r"Winner", proj))
        if announced and real:
            verdict = "won?" if won else "lost?"
            detail += f" · project ribbon={'YES' if won else 'none'}"
        elif announced:
            detail += " · project page unreadable(판정 보류)"
    elif announced:
        detail += " · project_url 미기록 — winners 목록 육안 확인 필요"
    return verdict, detail


def keyword(url, _):
    html = fetch(url)
    hits = re.findall(r"발표|수상자|선정 결과|winners?", html, re.I)
    return "pending", f"공지 키워드 {len(hits)}건 — 사람이 판정 (url 열람)"


def main():
    if "--force" not in sys.argv and os.path.exists(STATE):
        # 일 1회 가드 (tick 은 3h 주기 — 외부 사이트에 예의)
        if open(STATE).read().strip() == date.today().isoformat():
            print("result_check: already ran today (use --force)")
            return
    rows = []
    if os.path.exists(SOURCES):
        for line in open(SOURCES, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#") or line.startswith("key\t"):
                continue
            p = line.split("\t")
            rows.append(dict(zip(["key", "adapter", "url", "project_url", "note"],
                                 p + [""] * (5 - len(p)))))
    L = [f"# Result Check — {datetime.now():%Y-%m-%d %H:%M} (자동, 공개 페이지 기반)", "",
         "verdict `lost?`/`won?` 는 **제안**이다 — evidence 링크를 열어 확인 후 "
         "`ph settle close <key> --outcome … --evidence …` 로 확정한다.", "",
         "| key | verdict | detail | source |", "|---|---|---|---|"]
    suggestions = []
    for r in rows:
        fn = {"devpost": devpost, "keyword": keyword}.get(r["adapter"], keyword)
        verdict, detail = fn(r["url"], r["project_url"])
        L.append(f"| {r['key']} | {verdict} | {detail} | {r['url']} |")
        if verdict.endswith("?"):
            oc = verdict.rstrip("?")
            suggestions.append(f"ph settle close {r['key']} --outcome {oc} "
                               f"--evidence \"{r['url']} + {r['project_url']} ({date.today()})\"")
    if suggestions:
        L += ["", "## 제안 (확인 후 실행)", "", "```"] + suggestions + ["```"]
    L += ["", "> 로그인 필요한 결과(DACON 최종 LB 등)는 vault 자격증명 경로 — playbook/POSTERIOR.md §4.", ""]
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    os.replace(tmp, OUT)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    open(STATE, "w").write(date.today().isoformat())
    print(f"result_check: {len(rows)} sources, {len(suggestions)} suggestion(s) → RESULT_CHECK.md")


if __name__ == "__main__":
    main()
