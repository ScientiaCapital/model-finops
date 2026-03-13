#!/bin/bash
set -e

echo "==> model-finops init"

# Python venv for backend
echo "Setting up Python backend..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
pip install -r mcp/requirements.txt 2>/dev/null || true
deactivate

# Frontend deps
if [ -d "frontend" ]; then
  echo "Installing frontend deps..."
  cd frontend && npm install && cd ..
fi

echo ""
echo "Done. To start:"
echo "  Backend:  source .venv/bin/activate && python app/main.py"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Migrations: apply migrations/ SQL files in Supabase SQL editor"
