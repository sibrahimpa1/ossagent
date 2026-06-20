#!/bin/bash
set -e

echo "🌿 Setting up Ayurveda Recipe App"
echo ""

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install \
  fastapi \
  uvicorn \
  sqlalchemy \
  neo4j \
  qdrant-client \
  sentence-transformers \
  anthropic \
  python-dotenv \
  pydantic

# Create backend directory
mkdir -p backend

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created .env file from template"
  echo "→  Please add your ANTHROPIC_API_KEY to .env"
  echo ""
fi

echo ""
echo "========================================="
echo "✅ Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Add your ANTHROPIC_API_KEY to .env"
echo "  2. bash docker-setup.sh"
echo "  3. python build_graph.py"
echo "  4. python build_vectors.py"
echo "  5. bash start.sh"
echo ""
