#!/usr/bin/env bash
# CodeGraph one-shot launcher. Starts backend + frontend in parallel.
# Prereq: Ollama running with qwen2.5-coder:7b pulled.

set -e

cd "$(dirname "$0")"

cd backend
if [ ! -d ".venv" ]; then
  echo "[CodeGraph] Creating Python venv…"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "[CodeGraph] Starting backend on :8000…"
python main.py &
BACK_PID=$!
cd ..

cd frontend
if [ ! -d "node_modules" ]; then
  echo "[CodeGraph] Installing frontend deps…"
  npm install
fi
echo "[CodeGraph] Starting frontend on :5173…"
npm run dev &
FRONT_PID=$!
cd ..

trap "echo '[CodeGraph] Shutting down'; kill $BACK_PID $FRONT_PID 2>/dev/null || true; exit" INT TERM
wait
