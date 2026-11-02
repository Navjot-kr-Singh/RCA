#!/usr/bin/env bash
# One-time setup: one Python environment for the RCA API and the demo shop,
# then the offline tests. Needs Python 3.9+ and internet for pip.
# Usage: scripts/setup.sh        (PYTHON=python3.12 scripts/setup.sh to pick one)
set -euo pipefail
cd "$(dirname "$0")/.."

py="${PYTHON:-python3}"
if ! "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo "Python 3.9 or newer is needed (tried: $py)." >&2
  exit 1
fi

if [ ! -x Backend/.venv/bin/python ]; then
  echo "Creating Backend/.venv with $("$py" --version)"
  "$py" -m venv Backend/.venv
fi
echo "Installing packages (RCA API + demo shop)..."
Backend/.venv/bin/pip install -q --upgrade pip
Backend/.venv/bin/pip install -q -r Backend/requirements.txt -r demo-shop/requirements.txt

if [ ! -f Backend/.env ]; then
  printf 'OPENAI_API_KEY=\n' > Backend/.env
  echo "Created Backend/.env. Add an OpenAI key there for live answers, or use demo mode."
fi
chmod +x scripts/*.sh

echo "Running offline tests..."
(cd Backend && .venv/bin/python -m unittest -q tests.test_oncall tests.test_rag)
(cd demo-shop && ../Backend/.venv/bin/python -m unittest -q tests.test_shop)

cat <<'EOF'

Setup done. Start the two services in separate terminals:

  # RCA API on :8000. RCA_DEMO_MODE=1 needs no OpenAI key; drop it for live answers.
  cd Backend && RCA_DEMO_MODE=1 .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

  # Demo shop on :8001
  cd demo-shop && ../Backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001

Then break the shop and raise the alert:

  scripts/break.sh redis-oom && scripts/alert.sh
EOF
