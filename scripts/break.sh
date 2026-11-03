#!/usr/bin/env bash
# Trigger a controlled failure in the local demo shop.
# Usage: scripts/break.sh redis-oom|db-pool|bad-config
set -euo pipefail

source "$(dirname "$0")/lib.sh"
scenario="${1:-}"

checkouts() {
  for i in $(seq 1 "$1"); do
    curl -sS -o /dev/null -w "  checkout $i -> HTTP %{http_code}\n" -X POST "$SHOP_URL/checkout" \
      -H 'Content-Type: application/json' \
      -d '{"user_id": "demo-user", "items": ["tshirt"]}'
  done
}

case "$scenario" in
  redis-oom)
    echo "Breaking: cache limit -> 3 keys, eviction policy -> noeviction"
    curl -fsS -X POST "$SHOP_URL/admin/cache/config" \
      -H 'Content-Type: application/json' \
      -d '{"max_keys": 3, "policy": "noeviction"}'
    echo
    echo "Sending checkouts until the cache is full:"
    checkouts 4
    ;;
  db-pool)
    echo "Breaking: pool size -> 5, leaking 5 connections that are never returned"
    curl -fsS -X POST "$SHOP_URL/admin/db/config" \
      -H 'Content-Type: application/json' \
      -d '{"size": 5, "leak": 5}'
    echo
    echo "Sending checkouts while the pool is exhausted:"
    checkouts 2
    ;;
  bad-config)
    echo "Breaking: deploying release v2 (its config has a typo)"
    curl -fsS -X POST "$SHOP_URL/admin/deploy" \
      -H 'Content-Type: application/json' \
      -d '{"release": "v2"}'
    echo
    echo "Sending checkouts after the deploy:"
    checkouts 2
    ;;
  *)
    echo "Usage: $0 redis-oom|db-pool|bad-config" >&2
    exit 1
    ;;
esac
