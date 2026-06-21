# FoodPorn Ayurveda App - Deployment Guide

This guide covers deploying FoodPorn to replace ossagent on the existing VPS infrastructure.

## Pre-Deployment Checklist

### 1. Update CORS in Backend

Edit `backend/main.py` and ensure CORS allows your frontend domains:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.ossagent.net",           # Frontend production
        "https://ossagentapp-ujzb5.ondigitalocean.app",  # DigitalOcean App Platform
        "http://localhost:5173",               # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Environment Variables Required

Create a `.env` file on the VPS at `/opt/legal-rag-poc/.env` with:

```bash
# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_key_here
EXTRACTION_MODEL=claude-opus-4-8
SUGGESTION_MODEL=claude-sonnet-4-6

# Neo4j
NEO4J_PASSWORD=ayurveda123

# Admin
ADMIN_TOKEN=your_secure_admin_token_here

# Optional
QDRANT_HOST=qdrant
QDRANT_PORT=6333
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
```

### 3. Frontend Environment Variables

Update DigitalOcean App Platform environment variables:

- `VITE_API_URL=https://ossagent.net`
- (Remove `VITE_APP_PASSWORD` if no longer needed)

## VPS Deployment Steps

### Step 1: SSH into VPS

```bash
ssh root@178.128.250.32
```

### Step 2: Stop and Remove Old Containers

```bash
cd /opt/legal-rag-poc
docker compose down
```

### Step 3: Backup Old Data (Optional)

```bash
tar -czf ~/ossagent-backup-$(date +%Y%m%d).tar.gz \
  /opt/legal-rag-poc/data/qdrant \
  /opt/legal-rag-poc/data/neo4j \
  /opt/legal-rag-poc
```

### Step 4: Update Repository

The repo should already be configured at https://github.com/sibrahimpa1/ossagent

```bash
cd /opt/legal-rag-poc
git pull origin main
```

### Step 5: Create Required Directories

```bash
mkdir -p /opt/legal-rag-poc/data/neo4j
mkdir -p /opt/legal-rag-poc/data/qdrant
```

### Step 6: Create/Update .env File

```bash
nano /opt/legal-rag-poc/.env
```

Paste the environment variables from Section 2 above.

### Step 7: Build and Start Services

```bash
docker compose build
docker compose up -d
```

### Step 8: Monitor Startup

```bash
# Watch all container logs
docker compose logs -f

# Check specific service
docker compose logs -f app
```

### Step 9: Initialize Neo4j Graph Database

**Important:** You need to populate the Neo4j graph with recipes.

Option A - From your local machine:
```bash
# Export local Neo4j data
docker exec neo4j neo4j-admin dump --database=neo4j --to=/tmp/neo4j.dump

# Copy to VPS
scp /path/to/neo4j.dump root@178.128.250.32:/tmp/

# On VPS, import
docker exec foodporn_neo4j neo4j-admin load --from=/tmp/neo4j.dump --database=neo4j --force
docker compose restart neo4j
```

Option B - Rebuild graph on VPS:
```bash
# Copy chunks.json to VPS
scp data/chunks.json root@178.128.250.32:/opt/legal-rag-poc/data/

# SSH into VPS and run build script inside app container
ssh root@178.128.250.32
cd /opt/legal-rag-poc
docker compose exec app python -c "
import sys
sys.path.insert(0, '.')
from build_graph import GraphBuilder
builder = GraphBuilder()
builder.run()
"
```

### Step 10: Initialize Qdrant Vector Database

Similar to Neo4j, you need to populate Qdrant:

Option A - Copy Qdrant data directory:
```bash
# Stop Qdrant on VPS
docker compose stop qdrant

# Copy local Qdrant storage to VPS
rsync -avz --progress ./data/qdrant/ root@178.128.250.32:/opt/legal-rag-poc/data/qdrant/

# Restart Qdrant
docker compose start qdrant
```

Option B - Rebuild vectors on VPS:
```bash
# Copy chunks.json to VPS (if not done already)
scp data/chunks.json root@178.128.250.32:/opt/legal-rag-poc/data/

# SSH and run Qdrant ingestion script inside app container
ssh root@178.128.250.32
cd /opt/legal-rag-poc
docker compose exec app python -c "
# Add Qdrant ingestion code here
# (Create a separate script if needed)
"
```

### Step 11: Verify Deployment

```bash
# Check all containers are running
docker ps

# Test health endpoint
curl http://localhost:8000/health

# Test from outside (with HTTPS)
curl https://ossagent.net/health
```

Expected response:
```json
{"status": "healthy", "app": "FoodPorn Ayurveda RAG"}
```

### Step 12: Test API Endpoints

```bash
# Test profiles endpoint
curl https://ossagent.net/api/profiles

# Test creating a profile (requires ADMIN_TOKEN)
curl -X POST https://ossagent.net/api/profiles \
  -H "Content-Type: application/json" \
  -H "x-admin-token: YOUR_ADMIN_TOKEN" \
  -d '{"name": "Test Family"}'
```

## Frontend Deployment

The frontend auto-deploys via DigitalOcean App Platform when you push to main.

### Update Frontend API Client

Edit `frontend/src/api/client.js` to ensure it points to the correct backend:

```javascript
const API_URL = import.meta.env.VITE_API_URL || 'https://ossagent.net';
```

### Push to Deploy

```bash
git add .
git commit -m "Deploy FoodPorn Ayurveda app"
git push origin main
```

This will trigger:
1. Backend deployment via GitHub Actions (`.github/workflows/deploy.yml`)
2. Frontend deployment via DigitalOcean App Platform

## Post-Deployment Verification

### 1. Check Backend API

```bash
curl https://ossagent.net/health
```

### 2. Check Frontend

Visit https://app.ossagent.net in your browser.

### 3. Test Full Flow

1. Go to https://app.ossagent.net
2. Create a new profile
3. Add people with dosha types
4. Generate recipe suggestions
5. Verify suggestions load correctly

## Troubleshooting

### Container Not Starting

```bash
# Check logs
docker compose logs app

# Common issues:
# - Missing .env variables
# - Neo4j connection failed
# - Qdrant connection failed
```

### Neo4j Connection Issues

```bash
# Check Neo4j is running
docker compose ps neo4j

# Test connection
docker compose exec app python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'ayurveda123'))
driver.verify_connectivity()
print('✅ Connected to Neo4j')
"
```

### Qdrant Connection Issues

```bash
# Check Qdrant is running
docker compose ps qdrant

# Test connection
curl http://localhost:6333/collections
```

### CORS Errors

If you see CORS errors in browser console:

1. Check `backend/main.py` CORS middleware configuration
2. Ensure your frontend domain is in `allow_origins`
3. Rebuild backend: `docker compose build app && docker compose up -d app`

### SSL/TLS Issues

Caddy auto-manages certificates. If HTTPS fails:

```bash
# Check Caddy logs
docker compose logs caddy

# Verify Caddyfile syntax
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
```

## Rolling Back

If deployment fails and you need to roll back:

```bash
# On VPS
cd /opt/legal-rag-poc

# Stop new containers
docker compose down

# Restore from backup
tar -xzf ~/ossagent-backup-YYYYMMDD.tar.gz -C /

# Restart old version
docker compose up -d
```

## GitHub Actions Secrets

Ensure the following secret is set in GitHub repo settings:

- `VPS_SSH_KEY`: Private SSH key for root@178.128.250.32

To add/update:
1. Go to https://github.com/sibrahimpa1/ossagent/settings/secrets/actions
2. Add new secret named `VPS_SSH_KEY`
3. Paste your private SSH key content

## Data Persistence

The following directories persist data:

- `/opt/legal-rag-poc/data/neo4j` - Graph database
- `/opt/legal-rag-poc/data/qdrant` - Vector database
- `caddy_data` volume - SSL certificates
- `caddy_config` volume - Caddy configuration

**Important:** Don't delete these directories unless you want to lose all data.

## Monitoring

### View Live Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
docker compose logs -f neo4j
docker compose logs -f qdrant
docker compose logs -f caddy
```

### Check Resource Usage

```bash
docker stats
```

### Check Disk Usage

```bash
du -sh /opt/legal-rag-poc/data/*
```

## Performance Optimization

### Neo4j Memory

If you have more RAM available, edit `docker-compose.yml`:

```yaml
neo4j:
  environment:
    - NEO4J_dbms_memory_heap_max__size=4G  # Increase if needed
```

### Qdrant Performance

Qdrant storage is already optimized with local disk persistence.

## API Endpoints Reference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/health` | Health check | None |
| GET | `/api/profiles` | List profiles | None |
| POST | `/api/profiles` | Create profile | Admin token |
| GET | `/api/profiles/{id}` | Get profile | None |
| POST | `/api/profiles/{id}/people` | Add person | Admin token |
| POST | `/api/profiles/{id}/suggestions` | Get recipes | None |

## Support

For issues:
1. Check container logs: `docker compose logs -f app`
2. Verify environment variables: `cat /opt/legal-rag-poc/.env`
3. Test database connections (see Troubleshooting section)
4. Check GitHub Actions deployment logs

---

**Last Updated:** 2026-06-21
**Infrastructure:** DigitalOcean VPS (178.128.250.32)
**Domains:** ossagent.net (API), app.ossagent.net (Frontend)
