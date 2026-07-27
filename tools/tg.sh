#!/usr/bin/env bash
# Telegram 발신. 자격증명: ~/.config/prizehunter/telegram.env (TG_BOT_TOKEN, TG_CHAT_ID), mode 600.
# 사용: bash tools/tg.sh "메시지"
set -uo pipefail
CFG="${TG_CFG:-$HOME/.config/prizehunter/telegram.env}"
[ -f "$CFG" ] && . "$CFG"
: "${TG_BOT_TOKEN:?토큰없음 — ~/.config/prizehunter/telegram.env 에 TG_BOT_TOKEN/TG_CHAT_ID 설정}"
: "${TG_CHAT_ID:?chat_id없음}"
curl -s -m 15 "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TG_CHAT_ID}" \
  --data-urlencode "text=${1:?usage: tg.sh \"msg\"}" \
  -d "parse_mode=Markdown" -o /dev/null -w "tg send: %{http_code}\n"
