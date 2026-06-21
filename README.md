# Rasa - Ayurveda Recipe Recommender

A personal Ayurvedic recipe recommendation system powered by **dual-store RAG** architecture, combining Neo4j knowledge graphs with Qdrant vector search and Claude AI.

## Overview

This application provides personalized Ayurvedic recipe recommendations based on individual dosha constitutions and health imbalances. It uses a sophisticated dual-store retrieval system that mirrors the OSSAgent legal RAG pattern:

1. **Graph Store (Neo4j)**: Structured knowledge about recipes, ingredients, doshas, imbalances, and their relationships
2. **Vector Store (Qdrant)**: Semantic search over Ayurvedic theory and wisdom texts
3. **LLM (Claude Sonnet 4)**: Final synthesis and personalized recommendations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                 │
│                    Static on GitHub Pages                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                         │
│                    localhost:8000                           │
└──┬────────┬─────────┬──────────┬────────────────────────────┘
   │        │         │          │
   │ Neo4j  │ Qdrant  │ SQLite   │ Claude API
   │        │         │          │
   ▼        ▼         ▼          ▼
┌────┐  ┌────┐    ┌────┐     ┌─────┐
│Neo4j│  │Qdrant│  │SQLite│   │Claude│
│7687│  │6333│    │.db   │   │API  │
└────┘  └────┘    └────┘     └─────┘
```

## Tech Stack

**Frontend**:
- React 18 + Vite
- React Router for navigation
- Cormorant Garamond + Inter fonts
- Warm Ayurvedic color palette

**Backend**:
- FastAPI (Python)
- SQLAlchemy + SQLite (user profiles, people, history)
- Neo4j (recipe knowledge graph)
- Qdrant (theory vector store)
- Anthropic Claude Sonnet 4
- sentence-transformers (all-MiniLM-L6-v2)

**Infrastructure**:
- Docker (Neo4j + Qdrant containers)
- Local development server

## Data Source

Pre-processed data in `data/chunks.json`:
- **407 chunks** from 4 Ayurveda cookbooks
- **289 recipe chunks** → indexed in Neo4j
- **118 theory chunks** → vectorized in Qdrant

## Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker Desktop
- Anthropic API key ([get one here](https://console.anthropic.com/))

### Step 1: Clone and Install Dependencies

```bash
cd /Users/senks/Desktop/FoodPorn

# Install Python dependencies
bash setup.sh

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Step 2: Configure Environment

```bash
# Copy template and add your API key
cp .env.example .env

# Edit .env and add:
# ANTHROPIC_API_KEY=your_key_here
```

### Step 3: Start Docker Databases

```bash
bash docker-setup.sh
```

This will:
- Start Neo4j on ports 7474 (browser) and 7687 (bolt)
- Start Qdrant on port 6333
- Wait for both to be ready

You can verify at:
- Neo4j browser: http://localhost:7474 (neo4j / ayurveda123)
- Qdrant dashboard: http://localhost:6333/dashboard

### Step 4: Build Knowledge Graph (Neo4j)

```bash
source venv/bin/activate
python build_graph.py
```

This script:
1. Seeds base ontology nodes (Doshas, Tastes, Qualities, etc.)
2. Extracts structured data from recipes using Claude API
3. Caches all extractions to `data/graph_extractions.json`
4. Writes ~289 recipe nodes + relationships to Neo4j

**Expected output**:
```
✅ Processed 289 recipes (X newly extracted, Y from cache)
✅ Wrote 289 recipes to Neo4j

📊 Graph Database Summary
   Recipe              289 nodes
   Ingredient          ~150 nodes
   Dosha                  3 nodes
   ...
```

**Runtime**: ~10-15 minutes for first run (Claude API calls). Subsequent runs use cache and take ~30 seconds.

### Step 5: Build Vector Store (Qdrant)

```bash
python build_vectors.py
```

This script:
1. Embeds ~118 theory chunks using sentence-transformers
2. Upserts to Qdrant collection "ayurveda_theory"
3. Adds dosha theory and meal type references

**Expected output**:
```
✅ Upserted 118 theory chunks
✅ Upserted 3 dosha theory references
✅ Upserted 8 meal type descriptions

📊 Vector Store Summary
   Total points: 129
```

**Runtime**: ~1-2 minutes

### Step 6: Start Application

```bash
bash start.sh
```

This starts:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173

API docs available at: http://localhost:8000/docs

## Usage

### 1. Create a Profile

On the home screen, click "New Profile" and give it a name (e.g., "Date Night", "Solo Cooking").

### 2. Add People

Click on your profile, then "Add Person":
- Enter name
- Set serving count (for larger appetites)
- Select **primary dosha** (required)
- Optionally select **secondary dosha**
- Check any **imbalances** they're experiencing

**Example**:
```
Name: Sarah
Serving count: 1
Primary dosha: Pitta
Secondary dosha: Vata
Imbalances: Inflammation, Acid-Reflux
```

### 3. Get Recommendations

Click "✨ Get Today's Recipes" to trigger the dual-store RAG pipeline:

1. **Graph query**: Neo4j finds recipes that balance all primary doshas and help with imbalances
2. **Vector query**: Qdrant finds relevant Ayurvedic wisdom about those doshas/imbalances
3. **Claude synthesis**: Receives top 15 graph recipes + top 5 theory chunks, returns 6-8 best selections with personalized explanations

### 4. View History

Click "📜 History" to see past suggestions with full context about who was cooking and what was recommended.

## How the Dual-Store RAG Works

### Graph Query (Neo4j)

Cypher query finds recipes matching:
- Must balance ALL primary doshas
- Must NOT aggravate any primary doshas
- Scored by: dosha balance (+3), imbalance help (+2), diversity (+1), season (+2)

Returns top 15 recipes with full relationship context.

### Vector Query (Qdrant)

Builds semantic query from people's profiles:
```
"Ayurvedic diet for Pitta, Vata dosha.
Managing Inflammation, Acid-Reflux.
Foods that balance and nourish."
```

Embeds with sentence-transformers, searches Qdrant with dosha filter, returns top 5 theory chunks.

### Claude Prompt

Combines:
- People profiles (doshas, imbalances, serving counts)
- 15 graph recipes with scores and per-person reasoning
- 5 theory chunks for context
- Current season

Claude selects 6-8 final recipes considering:
- Meal type variety
- Complementary tastes/qualities
- Specific imbalances
- Seasonal appropriateness

Returns structured JSON with warm, personalized explanations using people's names.

## File Structure

```
.
├── backend/
│   ├── main.py          # FastAPI app with all endpoints
│   ├── models.py        # SQLAlchemy models
│   ├── database.py      # DB session management
│   └── rag.py           # Dual-store RAG system
├── frontend/
│   ├── src/
│   │   ├── screens/     # HomeScreen, ProfileScreen, SuggestionScreen, HistoryScreen
│   │   ├── components/  # DoshaChip, Button, Modal, LoadingSpinner
│   │   ├── api/         # API client
│   │   └── App.jsx      # Router
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── chunks.json              # Source data (committed)
│   ├── graph_extractions.json   # Claude cache (gitignored)
│   ├── neo4j/                   # Neo4j volume (gitignored)
│   ├── qdrant_storage/          # Qdrant volume (gitignored)
│   └── ayurveda.db              # SQLite DB (gitignored)
├── build_graph.py       # Populate Neo4j
├── build_vectors.py     # Populate Qdrant
├── docker-setup.sh      # Start Docker containers
├── setup.sh             # Install dependencies
├── start.sh             # Start backend + frontend
├── .env                 # Environment variables
└── README.md
```

## API Endpoints

### Profiles
- `GET /profiles` - List all profiles
- `POST /profiles` - Create profile
- `DELETE /profiles/{id}` - Delete profile

### People
- `GET /profiles/{id}/people` - Get people in profile
- `POST /profiles/{id}/people` - Add person
- `PUT /people/{id}` - Update person
- `DELETE /people/{id}` - Delete person

### Suggestions
- `POST /profiles/{id}/suggest` - Generate recommendations (dual-store RAG)

### History
- `GET /profiles/{id}/history` - Get suggestion history

### Health
- `GET /health` - System health check

## Development

### Running Tests

```bash
# Backend (from project root)
source venv/bin/activate
pytest

# Frontend
cd frontend
npm test
```

### Rebuilding Database

To reset and rebuild from scratch:

```bash
# Stop containers
docker stop neo4j qdrant

# Remove data
rm -rf data/neo4j data/qdrant_storage data/graph_extractions.json data/ayurveda.db

# Rebuild
bash docker-setup.sh
python build_graph.py
python build_vectors.py
```

### Inspecting the Graph

Neo4j browser queries:

```cypher
// Count nodes by type
MATCH (n:Recipe) RETURN count(n)
MATCH (n:Ingredient) RETURN count(n)

// Find recipes for Vata
MATCH (r:Recipe)-[:BALANCES]->(d:Dosha {name: 'Vata'})
RETURN r.name, r.source_book
LIMIT 10

// Find recipes that help with anxiety
MATCH (r:Recipe)-[:HELPS_WITH]->(i:Imbalance {name: 'Anxiety'})
RETURN r.name, r.source_book

// Explore full graph structure
MATCH (r:Recipe {name: 'Coconut and Cilantro Kitchari'})
OPTIONAL MATCH (r)-[rel]->(target)
RETURN r, rel, target
```

## Design System

### Colors
- Background: `#FEFAF4` (warm cream)
- Surface: `#FFFFFF`
- Primary: `#C4611A` (saffron)
- Accent: `#7B9E4E` (herb green)
- Text: `#2C1810` (deep brown)

### Dosha Colors
- Vata: `#7B6FA0` (violet)
- Pitta: `#C4611A` (saffron)
- Kapha: `#4A7C6E` (teal)

### Fonts
- Headings: Cormorant Garamond (serif)
- Body: Inter (sans-serif)

## Troubleshooting

### "Health check failed: neo4j_recipe_count = 0"

Run `python build_graph.py` to populate Neo4j.

### "Failed to load profiles: HTTP 500"

Check that:
1. Docker containers are running: `docker ps`
2. Backend is running: `curl http://localhost:8000/health`
3. Check backend logs for errors

### Claude API errors

Check:
1. `.env` has valid `ANTHROPIC_API_KEY`
2. You have API credits remaining
3. Rate limits (batch size = 5, delay = 1s)

### Frontend not loading

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

## Deployment

### Frontend (GitHub Pages)

```bash
cd frontend
npm run build
# Upload dist/ to GitHub Pages
```

### Backend

Backend runs locally only. For production:
1. Deploy FastAPI to cloud (AWS, GCP, Azure)
2. Use managed Neo4j (Neo4j Aura)
3. Use managed Qdrant (Qdrant Cloud)
4. Update CORS origins in `backend/main.py`

## License

Private internal tool for personal use.

## Credits

Built with:
- [Claude AI](https://anthropic.com) by Anthropic
- [Neo4j](https://neo4j.com) graph database
- [Qdrant](https://qdrant.tech) vector database
- [FastAPI](https://fastapi.tiangolo.com)
- [React](https://react.dev)
- [sentence-transformers](https://www.sbert.net)

Recipe data from 4 Ayurvedic cookbooks (see `data/chunks.json` for sources).
