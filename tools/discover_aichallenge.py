#!/usr/bin/env python3
"""Discover AI Challenge for All tracks from the rendered competition page.

The site is a Next.js app, so generic curl scraping can see shell HTML but not
the rendered table reliably. This adapter uses the existing fetch_render.py
helper, then extracts the table text with standard-library HTML stripping.
"""
import argparse
import html
import os
import re
import subprocess


HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.abspath(os.path.join(HERE, ".."))
URL = "https://aichallenge4all.or.kr/competitions"


def render(url):
    return subprocess.check_output(
        ["python3", os.path.join(HERE, "fetch_render.py"), url, "--scroll", "3"],
        text=True,
        errors="ignore",
        timeout=120,
    )


def text_lines(page):
    page = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", page, flags=re.I)
    page = re.sub(r"<[^>]+>", "\n", page)
    out = []
    for line in html.unescape(page).splitlines():
        line = " ".join(line.split())
        if line:
            out.append(line)
    return out


def krw(prize_text):
    best = 0
    for count, amount in re.findall(r"(\d+)\s*점\s*/\s*([0-9,]+)\s*만원", prize_text):
        best = max(best, int(amount.replace(",", "")) * 10_000)
    for amount in re.findall(r"([0-9,]+)\s*만원", prize_text):
        best = max(best, int(amount.replace(",", "")) * 10_000)
    if "5억원" in prize_text or "5억" in prize_text:
        best = max(best, 500_000_000)
    return best


def classify(name, prize_text):
    if "경품" in prize_text or "추첨" in prize_text:
        return "lottery", "no"
    if "로보틱스" in name:
        return "robotics", "no"
    if "창작" in name:
        return "vision", "yes"
    if "기상" in name or "데이터" in name or "해커톤" in name:
        return "ml", "yes"
    if "활용 사례" in name or "활용대회" in name:
        return "ml", "yes"
    if "퀴즈" in name:
        return "nlp", "yes"
    return "ml", "yes"


def parse(lines):
    rows = []
    seen = {}
    for i, line in enumerate(lines):
        if not re.search(r"AI|인공지능|로보틱스|기상|문화체육관광|클릭온", line):
            continue
        if line in {"일정", "시상규모", "상태", "접수중", "종료", "예선"}:
            continue
        window = lines[i + 1 : i + 6]
        schedule = next((x for x in window if re.search(r"월|시즌|접수|예선|결선|온라인", x)), "")
        prize = next((x for x in window if re.search(r"만원|억원|경품|상금|추첨", x)), "")
        status = "접수중" if "접수중" in window else "종료" if "종료" in window else ""
        if not prize and not schedule:
            continue
        if status == "종료":
            continue
        if line in seen:
            prev = seen[line]
            if prev["note"].count("접수중") <= f"{status}; {schedule}; {prize}".count("접수중"):
                continue
        domain, edge = classify(line, prize)
        prize_krw = krw(prize)
        if "기상" in line:
            days = 20
        elif "문화체육관광" in line:
            days = 13
        elif "활용 사례" in line:
            days = 140
        elif "챔피언" in line or "루키" in line:
            days = 183
        else:
            days = 60
        item = {
                "name": f"AIC {line}",
                "domain": domain,
                "prize": str(prize_krw),
                "metric": "judged" if domain != "nlp" else "accuracy",
                "data_modality": "multimodal" if domain in {"vision", "robotics"} else "tabular",
                "hardware_required": "robot" if domain == "robotics" else "none",
                "external_data_policy": "open",
                "days_to_deadline": str(days),
                "eligibility": "open",
                "we_have_edge": edge,
                "note": f"{status}; {schedule}; {prize}".strip("; "),
            }
        seen[line] = item
    return list(seen.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(CONTROL, "candidates_aic.tsv"))
    args = ap.parse_args()

    rows = parse(text_lines(render(URL)))
    rows = [r for r in rows if r["prize"] != "0" or "경품" in r["note"]]

    cols = [
        "name",
        "domain",
        "prize",
        "metric",
        "data_modality",
        "hardware_required",
        "external_data_policy",
        "days_to_deadline",
        "eligibility",
        "we_have_edge",
        "note",
    ]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        f.write("# source: https://aichallenge4all.or.kr/competitions rendered live\n")
        for r in rows:
            f.write("\t".join(r.get(c, "") for c in cols) + "\n")
    print(args.out)
    print(f"discovered={len(rows)} aichallenge tracks")


if __name__ == "__main__":
    main()
