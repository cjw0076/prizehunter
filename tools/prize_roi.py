#!/usr/bin/env python3
"""prize_roi.py — the business brain: prize-vs-difficulty ROI scoring.

Policy: "돈 되는 것만 한다." Rank discovered contests by EXPECTED VALUE PER EFFORT
and hard-filter out low/no-prize ones. For each candidate it fetches the detail
page, extracts the prize (max KRW near 상금/시상/대상), estimates effort + agent
win-probability from the title/category, and computes:

  expected_value = prize_total * win_prob
  roi            = expected_value / effort_hours      (KRW per agent-hour)

Effort & fit by deliverable type (agent reality):
  text/idea (아이디어·기획·네이밍·슬로건·독후감·수기·정책·리포트·논문) -> low effort, high fit
  build (앱·웹·IT·SW·데이터·AI·창업)                                  -> mid effort, high fit (our core)
  media (영상·UCC·사진·디자인·웹툰·포스터)                            -> higher effort, mid fit (prod tools)
  offline/모집/캠퍼스/멘토                                            -> NOT a prize contest -> drop

Usage: prize_roi.py [--candidates candidates_contests.tsv] [--floor 1000000] [--fetch]
"""
import re, os, subprocess, argparse, html

def fetch(url):
    try:
        return subprocess.check_output(
            ['curl','-L','--connect-timeout','8','--max-time','20','-sA','Mozilla/5.0',url],
            text=True, errors='ignore')
    except Exception:
        return ''

WON = re.compile(r'([0-9][0-9,]*)\s*(억|천만|만)\s*원?')
PRIZE_CONTEXT = re.compile(r'상금|시상|시상금|대상|최우수|우수상|장려|수상|상장|상패|총\s*상금')
DROP_TITLE = re.compile(r'^\s*(AD\.|광고\b)|host a hackathon', re.I)
# 단일 대회 상금이 ₩20억을 넘는 파싱 결과는 거의 항상 오류(누적 실적·무관 숫자 혼입).
# 사람이 검증하기 전까지 ROI 랭킹에서 제외하고 별도 섹션에 격리한다 — 쓰레기 파싱이
# ROI 보드 최상단을 차지해 자원 배분을 왜곡하던 문제의 가드.
SUSPECT_PRIZE_MAX = 2_000_000_000

def visible_text(text):
    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', text)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text)

def won_value(match):
    n = int(match.group(1).replace(',', ''))
    unit = match.group(2)
    return n * (100_000_000 if unit=='억' else 10_000_000 if unit=='천만' else 10_000)

def krw(text):
    """largest KRW amount mentioned in prize/award context; 0 if none.

    The old version took the largest currency-looking number anywhere on the
    page. Contest listing sites contain ads, unrelated rankings, and navigation
    snippets, so that created fake ROI. Require a local prize context window.
    """
    text = visible_text(text)
    best = 0
    for m in WON.finditer(text):
        ctx = text[max(0, m.start()-90):m.end()+90]
        if PRIZE_CONTEXT.search(ctx):
            best = max(best, won_value(m))
    # also plain "총상금 20,000,000"
    for m in re.finditer(r'(?:총\s*)?상금[^0-9]{0,12}([0-9][0-9,]{5,})', text):
        best = max(best, int(m.group(1).replace(',', '')))
    return best

def classify(title):
    t = title
    if DROP_TITLE.search(t):
        return ('non_contest', 999, 0.0)          # ad/platform listing, not a contest target
    if re.search(r'모집|캠퍼스|멘토|아카데미|설명회|참가자|기수|채용', t):
        return ('non_contest', 999, 0.0)          # not a prize contest -> drop
    if re.search(r'아이디어|기획|네이밍|슬로건|독후감|수기|정책|리포트|논문|에세이|글쓰기|작명|제안', t):
        return ('text', 4, 0.30)                   # low effort, strong agent fit
    if re.search(r'앱|웹|IT|SW|소프트|데이터|인공지능|\bAI\b|창업|해커톤|개발|알고리즘|코딩', t):
        return ('build', 16, 0.25)                 # our core; mid effort
    if re.search(r'영상|UCC|사진|디자인|캐릭터|웹툰|포스터|그림|미술|음악|굿즈', t):
        return ('media', 24, 0.12)                 # needs production; lower fit
    return ('other', 12, 0.12)

def dday(text):
    m = re.search(r'D-(\d{1,3})', text)
    return int(m.group(1)) if m else None

def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(__file__)
    ap.add_argument('--candidates', default=os.path.join(here,'..','candidates_contests.tsv'))
    ap.add_argument('--floor', type=int, default=1_000_000, help='min prize KRW ("돈 되는 것만")')
    ap.add_argument('--fetch', action='store_true', help='fetch detail pages for prize (slower, accurate)')
    ap.add_argument('--out', default=os.path.join(here,'..','ROI_REPORT.md'))
    a = ap.parse_args()

    rows, hdr = [], None
    for line in open(a.candidates):
        line=line.rstrip('\n')
        if not line or line.startswith('#'): continue
        c=line.split('\t')
        if hdr is None: hdr=c; continue
        rows.append(dict(zip(hdr,c)))

    scored=[]; suspects=[]
    for r in rows:
        title=r.get('name',''); kind,effort,winp = classify(title)
        prize=0; dd=None
        if kind=='non_contest':
            scored.append((-1,0,0,kind,None,title,r.get('url',''),'광고/모집/비공모 → drop')); continue
        if a.fetch and r.get('url'):
            page=fetch(r['url']); prize=krw(page); dd=dday(page)
        if prize > SUSPECT_PRIZE_MAX:
            suspects.append((prize, title, r.get('url','')))
            continue
        ev = prize*winp
        roi = ev/effort if effort else 0
        note=f"{kind} prize={prize:,} winp={winp} effort={effort}h"
        scored.append((roi,prize,ev,kind,dd,title,r.get('url',''),note))

    scored.sort(key=lambda x:(x[0],x[1]), reverse=True)
    with open(a.out,'w') as o:
        o.write('# Prize ROI Report — "돈 되는 것만"\n\n')
        o.write(f'- floor: prize ≥ {a.floor:,} KRW · fetched_prizes={a.fetch}\n')
        o.write('- ROI = (prize × agent_win_prob) / effort_hours  (KRW per agent-hour)\n\n')
        o.write('| ROI(₩/h) | prize | EV | kind | D- | contest |\n|---:|---:|---:|---|---:|---|\n')
        kept=0
        dropped=0
        for roi,prize,ev,kind,dd,title,url,note in scored:
            if kind=='non_contest':
                dropped += 1
                continue
            if a.fetch and prize < a.floor:
                dropped += 1
                continue
            kept+=1
            o.write(f'| {roi:,.0f} | {prize:,} | {ev:,.0f} | {kind} | {dd if dd is not None else "?"} | {title[:46]} |\n')
        o.write(f'\n{kept} contests pass the money floor. Dropped/filtered: {dropped}. Drop everything else.\n')
        if suspects:
            o.write(f'\n## ⚠️ Suspect prizes — 파싱 검증 필요 (cap ₩{SUSPECT_PRIZE_MAX:,} 초과, 랭킹 제외)\n\n')
            o.write('| parsed prize | contest |\n|---:|---|\n')
            for prize, title, _url in sorted(suspects, reverse=True):
                o.write(f'| {prize:,} | {title[:60]} |\n')
            o.write(f'\n{len(suspects)} row(s) quarantined — verify the real pool by hand before ranking.\n')
        o.write('\n> Verify prize (max-KRW heuristic), AI-content rules (text contests may forbid AI), eligibility before committing.\n')
    print(a.out)
    top=[s for s in scored if s[3]!='non_contest'][:5]
    print('TOP by ROI:')
    for roi,prize,ev,kind,dd,title,url,note in top:
        print(f'  ₩{roi:,.0f}/h  [{kind}] {title[:44]}  ({note})')

if __name__=='__main__':
    main()
