#!/usr/bin/env bash
# notify_founder.sh — deliver a completed submission package to the founder for confirmation.
# Two modes (auto-selected):
#   SMTP  : if the vault holds SMTP_APP_PASSWORD -> python smtplib really SENDS to the founder inbox.
#   DRAFT : otherwise -> writes a draft-request JSON; the agent then calls the Gmail MCP create_draft
#           (the Gmail MCP exposes no send verb, only drafts). Founder reviews/sends from Drafts.
# No secrets are printed or written outside the gitignored vault.
#   PRIZEHUNTER_NOTIFY_MODE=draft forces draft JSON generation without reading vault secrets.
#   usage: notify_founder.sh --key <K> --zip <zip> --guide <guide.md> [--dday D-NN] [--to addr]
set -euo pipefail
PH_HOME="$(cd -- "$(dirname "$0")/.." && pwd)"
VAULT="$PH_HOME/.vault"

key=""; zip=""; guide=""; dday=""; to="cjw070690@gmail.com"
while [ $# -gt 0 ]; do case "$1" in
  --key) key="$2"; shift 2;;
  --zip) zip="$2"; shift 2;;
  --guide) guide="$2"; shift 2;;
  --dday) dday="$2"; shift 2;;
  --to) to="$2"; shift 2;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done
[ -n "$key" ] && [ -f "$zip" ] || { echo "usage: notify_founder.sh --key K --zip Z [--guide G --dday D-NN]" >&2; exit 2; }

subj="[Prizehunter] ${key} 제출물 컨펌요청${dday:+ ($dday)}"
szb="$(stat -c%s "$zip")"
body_intro="$key 제출물이 완성되어 컨펌 요청드립니다.
- 패키지: $(basename "$zip") ($(du -h "$zip" | cut -f1))
- 로컬 경로: $zip
${dday:+- 마감: $dday}

아래 가이드/체크리스트 확인 후, 개인 서식 서명 → 포털 업로드 부탁드립니다.
외부 제출은 founder 컨펌 후 직접 진행됩니다(안전게이트).
"
guide_txt=""; [ -n "$guide" ] && [ -f "$guide" ] && guide_txt="$(cat "$guide")"

# ---- mode select ----
apppw=""
if [ "${PRIZEHUNTER_NOTIFY_MODE:-}" != "draft" ] && [ -f "$VAULT/identity.env" ]; then
  apppw="$(sed -n 's/^SMTP_APP_PASSWORD=//p' "$VAULT/identity.env" | head -1 | tr -d '"' )"
fi

if [ -n "$apppw" ] && [ "$szb" -le 26214400 ]; then
  # ---- SMTP MODE: really send ----
  SENDER="$(sed -n 's/^GOOGLE_EMAIL=//p' "$VAULT/identity.env" | head -1 | tr -d '"')"; SENDER="${SENDER:-$to}"
  SMTP_APP_PASSWORD="$apppw" SENDER="$SENDER" TO="$to" SUBJ="$subj" \
  ZIP="$zip" BODY="$body_intro
$guide_txt" python3 - <<'PY'
import os, smtplib, ssl
from email.message import EmailMessage
z=os.environ["ZIP"]
ctx=ssl.create_default_context()
def build(attach):
    m=EmailMessage()
    m["From"]=os.environ["SENDER"]; m["To"]=os.environ["TO"]; m["Subject"]=os.environ["SUBJ"]
    body=os.environ["BODY"]
    if not attach:
        body=("[패키지: %s] (Gmail이 스크립트 포함 zip을 보안차단하여 첨부 대신 로컬경로 안내. 같은 머신에서 직접 접근)\n\n" % os.path.abspath(z))+body
    m.set_content(body)
    if attach:
        with open(z,"rb") as f: data=f.read()
        m.add_attachment(data, maintype="application", subtype="zip", filename=os.path.basename(z))
    return m
with smtplib.SMTP("smtp.gmail.com",587) as s:
    s.starttls(context=ctx); s.login(os.environ["SENDER"], os.environ["SMTP_APP_PASSWORD"])
    try:
        s.send_message(build(True)); print("SENT via SMTP (zip 첨부) to", os.environ["TO"])
    except smtplib.SMTPDataError as e:
        # Gmail 552 보안차단(스크립트 포함 zip) → 첨부 없이 로컬경로 인라인 폴백
        if e.smtp_code==552:
            s.send_message(build(False)); print("SENT via SMTP (첨부차단→인라인폴백) to", os.environ["TO"])
        else: raise
PY
  echo "MODE=SMTP"
else
  # ---- DRAFT MODE: emit a draft-request the agent feeds to Gmail MCP create_draft ----
  req="$PH_HOME/EXIT/packages/${key}_draft_request.json"
  attach="false"; [ "$szb" -le 26214400 ] && attach="true"
  TO="$to" SUBJ="$subj" REQ="$req" ZIP="$zip" ATTACH="$attach" BODY="$body_intro
$guide_txt" python3 - <<'PY'
import os, json
json.dump({
  "to":[os.environ["TO"]],
  "subject":os.environ["SUBJ"],
  "body":os.environ["BODY"],
  "zip_path":os.environ["ZIP"],
  "attach_ok":os.environ["ATTACH"]=="true",
}, open(os.environ["REQ"],"w"), ensure_ascii=False, indent=2)
print("draft-request written:", os.environ["REQ"])
PY
  echo "MODE=DRAFT"
  [ "$attach" = "true" ] && echo "ATTACH=ok(≤25MB)" || echo "ATTACH=skip(>25MB; body carries path)"
  echo "DRAFT_REQUEST=$req"
  echo "→ agent: call Gmail MCP create_draft with this payload (no send verb available)."
fi
