#!/usr/bin/env bash
# Turnkey local runner for the NTS Vibe Checker pipeline.
#
#   ./run.sh https://hiddengarden.nl/     # scrape + score one festival
#   ./run.sh                              # Lowlands (default)
#   ./run.sh <url> --force                # ignore caches
#
# Handles venv + deps automatically. Needs an Anthropic key in pipeline/.env
# (ANTHROPIC_API_KEY=sk-ant-...) or exported in the environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/pipeline"

if [ ! -d .venv ]; then
  echo ">> venv aanmaken..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo ">> dependencies checken..."
pip install -q -r requirements.txt

if [ ! -f .env ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo ""
  echo "!! Geen API-key gevonden."
  echo "   Maak pipeline/.env met:  ANTHROPIC_API_KEY=sk-ant-..."
  echo "   (of: export ANTHROPIC_API_KEY=sk-ant-... )"
  exit 1
fi

python build.py "$@"

echo ""
echo ">> Klaar. Output staat in frontend/public/."
echo "   Preview lokaal:  cd frontend && npm install && npm run dev"
echo "   Dan in de browser:  http://localhost:5173/?f=<festival-id>"
