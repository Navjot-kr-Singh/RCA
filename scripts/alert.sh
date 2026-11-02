#!/usr/bin/env bash
# Probe the local demo shop and, if checkout is failing, print an incident alert.
# With ALERT_WEBHOOK_URL set to a Discord webhook, also post it to that channel.
# With ALERT_MENTION set (for example '<@&123>', the triager's role mention),
# the posted alert starts with it so the triager picks it up.
# To find the mention, send "\@<team>-triager" in Discord and copy what it shows.
# Usage: scripts/alert.sh
set -euo pipefail

source "$(dirname "$0")/lib.sh"

# Synthetic check: place a test order the way a customer would.
body_file=$(mktemp)
code=$(curl -s -o "$body_file" -w "%{http_code}" -X POST "$SHOP_URL/checkout" \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "synthetic-probe", "items": ["tshirt"]}')
body=$(cat "$body_file")
rm -f "$body_file"

if [ "$code" = "200" ]; then
  echo "No incident: synthetic checkout returned HTTP 200."
  exit 0
fi

alert="🚨 [ALERT] demo-shop: checkout is failing
time:     $(date -u +%Y-%m-%dT%H:%M:%SZ)
service:  demo-shop ($SHOP_URL)
check:    synthetic POST /checkout -> HTTP $code
response: $body"
echo "$alert"

if [ -n "${ALERT_WEBHOOK_URL:-}" ]; then
  case "$ALERT_WEBHOOK_URL" in
    https://discord.com/api/webhooks/*) ;;
    *) echo "Not sent: ALERT_WEBHOOK_URL must be a Discord webhook URL." >&2; exit 1 ;;
  esac
  content="$alert"
  if [ -n "${ALERT_MENTION:-}" ]; then
    content="${ALERT_MENTION} new alert:
$alert"
  fi
  # json.dumps escapes the quotes and newlines in the alert text.
  payload=$(printf '%s' "$content" | python3 -c 'import json, sys; print(json.dumps({"content": sys.stdin.read(), "allowed_mentions": {"parse": ["roles", "users"]}}))')
  curl -fsS -o /dev/null -X POST "$ALERT_WEBHOOK_URL" -H 'Content-Type: application/json' -d "$payload"
  echo "Sent to Discord."
fi
