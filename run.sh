#!/usr/bin/env bash
# One-time launcher: install deps, then start the Streamlit system.
# Usage: ./run.sh   (run from anywhere; cd's to the project folder itself)
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Installing dependencies (requirements.txt)..."
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> No .env found — copying .env.example. Fill in your API key before using the LLM agents."
  cp .env.example .env
fi

echo "==> Starting Streamlit (data-onboarding gate + coordination panel)..."
export PYTHONPATH="$PWD"
exec streamlit run ui/streamlit_app.py
