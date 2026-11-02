#!/usr/bin/env bash
# Trigger a controlled failure in the local demo shop.
# Usage: scripts/break.sh redis-oom
set -euo pipefail

source "$(dirname "$0")/lib.sh"
scenario="${1:-}"

case "$scenario" in
  redis-oom)
    echo "Breaking: cache limit -> 3 keys, eviction policy -> noeviction"
    curl -fsS -X POST "$SHOP_URL/admin/cache/config" \
      -H 'Content-Type: application/json' \
      -d '{"max_keys": 3, "policy": "noeviction"}'
    echo
    echo "Sending checkouts until the cache is full:"
    for i in 1 2 3 4; do
      curl -sS -o /dev/null -w "  checkout $i -> HTTP %{http_code}\n" -X POST "$SHOP_URL/checkout" \
        -H 'Content-Type: application/json' \
        -d '{"user_id": "demo-user", "items": ["tshirt"]}'
    done
    ;;
  *)
    echo "Usage: $0 redis-oom" >&2
    exit 1
    ;;
esac
