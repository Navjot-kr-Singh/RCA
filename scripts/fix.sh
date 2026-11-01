#!/usr/bin/env bash
# Recover the local demo shop from a scenario started by break.sh, then verify.
# Usage: scripts/fix.sh redis-oom
set -euo pipefail

source "$(dirname "$0")/lib.sh"
scenario="${1:-}"

case "$scenario" in
  redis-oom)
    echo "Fixing: eviction policy -> allkeys-lru, cache limit -> 100 keys"
    curl -fsS -X POST "$SHOP_URL/admin/cache/config" \
      -H 'Content-Type: application/json' \
      -d '{"max_keys": 100, "policy": "allkeys-lru"}'
    echo
    ;;
  *)
    echo "Usage: $0 redis-oom" >&2
    exit 1
    ;;
esac

echo "Verifying:"
checkout_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SHOP_URL/checkout" \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "fix-check", "items": ["tshirt"]}')
health_code=$(curl -s -o /dev/null -w "%{http_code}" "$SHOP_URL/health")
echo "  checkout -> HTTP $checkout_code"
echo "  health   -> HTTP $health_code"

if [ "$checkout_code" != "200" ] || [ "$health_code" != "200" ]; then
  echo "Fix applied but the shop is still unhealthy." >&2
  exit 1
fi
echo "Recovered: checkout and health are both OK."
