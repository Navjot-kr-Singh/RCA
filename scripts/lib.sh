# Shared checks for the demo scripts. Source this file; don't run it directly.

SHOP_URL="${SHOP_URL:-http://127.0.0.1:8001}"

# Failure simulations must only ever hit the local sandbox.
case "$SHOP_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) echo "Refusing to run: SHOP_URL must point at localhost, got $SHOP_URL" >&2; exit 1 ;;
esac

if ! curl -s -o /dev/null "$SHOP_URL/health"; then
  echo "Demo shop is not reachable at $SHOP_URL. Start it first:" >&2
  echo "  cd demo-shop && ../Backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001" >&2
  exit 1
fi
