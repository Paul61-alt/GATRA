#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Radar backend on http://localhost:8000 ..."
cd "$ROOT/backend"
python3.11 -m uvicorn main:app --port 8000 &
BACKEND_PID=$!

echo "Starting Radar frontend on http://localhost:5500 ..."
cd "$ROOT/frontend-prototype"
python3.11 -m http.server 5500 &
FRONTEND_PID=$!

echo ""
echo "  Backend  → http://localhost:8000"
echo "  Frontend → http://localhost:5500"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
