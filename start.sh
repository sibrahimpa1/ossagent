#!/bin/bash
set -e

echo "🌿 Starting Ayurveda Recipe App"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
  echo "❌ Virtual environment not found. Run: bash setup.sh"
  exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
  echo "❌ .env file not found. Copy .env.example and add your ANTHROPIC_API_KEY"
  exit 1
fi

# Check if Docker containers are running
if ! docker ps | grep -q neo4j; then
  echo "⚠️  Neo4j container not running. Starting..."
  docker start neo4j || echo "Run: bash docker-setup.sh"
fi

if ! docker ps | grep -q qdrant; then
  echo "⚠️  Qdrant container not running. Starting..."
  docker start qdrant || echo "Run: bash docker-setup.sh"
fi

# Activate venv and start backend
echo "🚀 Starting FastAPI backend on port 8000..."
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 3

# Start frontend if it exists
if [ -d "frontend" ]; then
  echo "🚀 Starting Vite frontend on port 5173..."
  cd frontend && npm run dev &
  FRONTEND_PID=$!
  cd ..
else
  echo "⚠️  Frontend not found. Skipping frontend start."
fi

echo ""
echo "========================================="
echo "✨ Services started!"
echo "========================================="
echo ""
echo "Backend API:  http://localhost:8000"
echo "API docs:     http://localhost:8000/docs"
if [ -d "frontend" ]; then
  echo "Frontend:     http://localhost:5173"
fi
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for processes
wait $BACKEND_PID
if [ ! -z "$FRONTEND_PID" ]; then
  wait $FRONTEND_PID
fi
