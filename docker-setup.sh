#!/bin/bash
set -e

echo "🐳 Starting Neo4j and Qdrant containers..."
echo ""

# Create data directories if they don't exist
mkdir -p data/neo4j
mkdir -p data/qdrant_storage

# Stop and remove existing containers if they exist
echo "Cleaning up existing containers..."
docker rm -f neo4j 2>/dev/null || true
docker rm -f qdrant 2>/dev/null || true

echo ""
echo "Starting Neo4j..."
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/ayurveda123 \
  -v "$(pwd)/data/neo4j:/data" \
  neo4j:latest

echo "Starting Qdrant..."
docker run -d --name qdrant \
  -p 6333:6333 \
  -v "$(pwd)/data/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant

echo ""
echo "⏳ Waiting for databases to start..."
sleep 15

# Check if Neo4j is ready
echo "Checking Neo4j health..."
max_retries=30
retry_count=0
while [ $retry_count -lt $max_retries ]; do
  if curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo "✅ Neo4j is ready!"
    break
  fi
  retry_count=$((retry_count + 1))
  echo "Waiting... ($retry_count/$max_retries)"
  sleep 2
done

# Check if Qdrant is ready
echo "Checking Qdrant health..."
retry_count=0
while [ $retry_count -lt $max_retries ]; do
  if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant is ready!"
    break
  fi
  retry_count=$((retry_count + 1))
  echo "Waiting... ($retry_count/$max_retries)"
  sleep 2
done

echo ""
echo "========================================="
echo "✨ Databases are running!"
echo "========================================="
echo ""
echo "Neo4j Browser:  http://localhost:7474"
echo "  Username: neo4j"
echo "  Password: ayurveda123"
echo ""
echo "Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "========================================="
echo "Next steps:"
echo "  1. python build_graph.py"
echo "  2. python build_vectors.py"
echo "  3. bash start.sh"
echo "========================================="
