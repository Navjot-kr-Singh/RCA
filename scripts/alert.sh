#!/usr/bin/env bash
# Probe the local demo shop and, if checkout is failing, print an incident alert
# ready to post in the incident channel.
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

cat <<ALERT
🚨 [ALERT] demo-shop: checkout is failing
time:     $(date -u +%Y-%m-%dT%H:%M:%SZ)
service:  demo-shop ($SHOP_URL)
check:    synthetic POST /checkout -> HTTP $code
response: $body
ALERT
