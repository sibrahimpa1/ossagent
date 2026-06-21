# RAG Improvement Master Prompt

Use this prompt when redesigning or upgrading the FoodPorn / Rasa Ayurveda recipe recommendation system. It reflects how the app **actually works today** and where the biggest quality gains live.

---

## Copy-paste prompt (for an AI engineer or coding agent)

```
You are upgrading an Ayurvedic meal recommendation RAG for a multi-person “table” app.

## Current architecture (do not break without replacing)

**Dual-store RAG** (pattern inspired by legal OSSAgent RAG):

1. **Neo4j graph store** — structured Ayurvedic knowledge
   - Nodes: Recipe, Ingredient, Dosha, Imbalance, Taste, Quality, Season, MealType, Book
   - Key edges: BALANCES, AGGRAVATES, HELPS_WITH, CONTAINS, SUITS_SEASON, MEAL_TYPE
   - Graph query: find recipes that BALANCE all doshas at the table and do NOT AGGRAVATE primary/secondary doshas
   - Scoring: +3 primary dosha balance, +1 secondary, +2 per imbalance helped, -5 if aggravates primary, +1 meal-type diversity, +2 seasonal fit

2. **Qdrant vector store** — Ayurvedic theory / wisdom chunks
   - Collection: ayurveda_theory
   - Embeddings: sentence-transformers/all-MiniLM-L6-v2
   - Filtered by dosha overlap; semantic query built from table doshas + imbalance names

3. **Claude (Anthropic)** — final curator / explainer
   - Input: people profiles + graph recipe candidates + vector wisdom + variety constraints
   - Output: strict JSON with:
     - `combined`: 3 shared-meal recipes + meal_harmony_note
     - `individual[]`: per-person solo meals (2 recipes each when 2+ people)
   - Each recipe: name, source, overall_fit, why_it_works, best_for, substitutions, ingredients[], per_person[]

**People model (critical for personalization):**
- Primary doshas (multi-select) with tendency: excess | deficiency
- Imbalance doshas (multi-select, excess only)
- Named imbalances per dosha (e.g. Anxiety, Acid-Reflux, Congestion) — must match graph Imbalance nodes
- Table size = number of people (no separate servings field in UI)

**Product rules:**
- Suggestions cached per table per calendar day; Regenerate creates a new session
- **7-day variety**: deprioritize recipes suggested in last 7 days; only repeat if pool is exhausted
- History tracks full JSON + cooked markers
- Custom user recipes stored in SQLite with doshas + imbalances

## Your mission

Design and implement a **meaningfully better** RAG pipeline that feels like a wise Ayurvedic chef who knows this table personally — not a static search engine that returns the same kitchari every time.

## Quality bar (“AMAZING” means)

1. **Personal** — speaks to each person by name; references their excess/deficiency tendency and named imbalances
2. **Grounded** — every suggested recipe must trace to graph evidence OR cited book source; no hallucinated “ Ayurveda says…” without a candidate
3. **Varied** — different meals day-to-day; rotates meal types ( breakfast / lunch / dinner / drink / soup ); avoids 7-day repeats
4. **Harmonious** — combined meals explain how one menu balances conflicting doshas at one table (e.g. cooling garnish for Pitta while base supports Vata)
5. **Actionable** — ingredients list, substitutions, per-person notes (“Senka: skip chili flakes”)
6. **Seasonally aware** — dynamic season from date (Winter/Spring/Summer/Fall), not hardcoded
7. **Two modes** — shared table vs solo meals; solo picks optimize for one person only

## Required improvements (prioritized)

### P0 — Retrieval quality
- [ ] Expand graph candidate pool (40+ recipes) before scoring; don’t LIMIT 10
- [ ] Soft-exclude recent recipes (7-day history per profile) in ranking, hard-exclude only when enough alternatives exist
- [ ] Shuffle within score tiers so Regenerate doesn’t return identical ordering
- [ ] Per-person graph queries for individual sections with separate exclude lists
- [ ] Include tendency in graph scoring (excess → favor pacifying qualities; deficiency → favor building/warming)
- [ ] Weight named imbalances higher than generic dosha balance (+3 imbalance match vs +2 today)

### P0 — LLM curation
- [ ] System prompt: “You may ONLY recommend recipes from the provided graph candidates unless explicitly allowed to adapt a nearby candidate”
- [ ] Pass full ingredient lists from graph (not 350-char truncation) for top 5 combined + top 3 per person
- [ ] Explicit JSON schema in prompt; validate response; retry once with compact mode
- [ ] Variety block: list recent recipe names; instruct model to prefer novel picks
- [ ] Temperature / diversity: consider asking for 5 candidates internally, return best 3

### P1 — Vector store
- [ ] Query per imbalance (“Managing Acid-Reflux with diet”) not just dosha names
- [ ] Retrieve 8–12 chunks, MMR diversify, pass top 4 to Claude
- [ ] Tag chunks with season + meal type metadata; filter by current season
- [ ] Rotate chunks day-to-day (exclude chunk_ids used in last 3 sessions)

### P1 — Ranking features
Add to graph score:
- Meal type coverage across the 3 combined picks (penalize 3 kitcharis)
- Cooked recipes in history (boost never-cooked, slight penalty for cooked 2+ times)
- Favorite recipes (small boost, not dominance)
- Prep time diversity for weeknight vs weekend (if metadata exists)

### P2 — Graph enrichment
- [ ] Ensure every Recipe has: meal_type, season, ingredients[], helps_with imbalances[]
- [ ] Link recipes to tastes/qualities used in reasoning
- [ ] Ingest custom recipes into graph as `:Recipe:Custom` for unified retrieval

### P2 — Evaluation
Build a small eval set:
- 5 synthetic tables (Vata+Pitta couple, Kapha solo, etc.)
- Metrics: dosha safety (% not aggravating), imbalance coverage, 7-day repeat rate, JSON validity, latency
- Log graph candidates + final picks for debugging

## Prompt structure (target template)

```
SYSTEM: Expert Ayurvedic nutritionist. Warm, specific, JSON-only. Never invent recipes outside candidates.

USER:
## People cooking today
[name, primary dosha (tendency), imbalance doshas, named imbalances]

## Graph candidates — combined table
[8 recipes with score, source, meal_type, helps_imbalances, qualities, tastes, FULL ingredients, excerpt]

## Graph candidates — solo: {name}
[6 recipes each person]

## Ayurvedic wisdom (MMR-selected)
[4 chunks with source]

## Variety — avoid if possible (last 7 days)
[recipe names]

## Task
Return JSON: combined (3 recipes) + individual (2 per person).
Rules:
- Prefer novel recipes not in variety list
- Combined set must span ≥2 meal types
- Cite source book for each recipe
- per_person note must mention imbalance or tendency when relevant
- Season: {dynamic_season}
```

## Anti-patterns to eliminate

- Same top-5 graph results every run (fixed LIMIT + deterministic sort)
- Claude picking recipes not in graph (hallucination)
- Truncated recipe text → weak ingredient lists
- Ignoring excess vs deficiency tendency
- Combined and individual sections recommending the same 3 dishes
- Static “Summer” season in June and December alike
- No connection between vector wisdom and final recipe choice (wisdom decorative only)

## Success criteria

After upgrade, a tester should observe:
1. Regenerate 3× in one day → mostly different recipes each time
2. Same table 7 days straight → no recipe repeats until day 8 (unless library tiny)
3. Adding a person’s Acid-Reflux imbalance → visibly more cooling/soothing picks with explanation
4. Combined section explains cross-person compromises in meal_harmony_note
5. p95 latency stays under 35s (or async job + polling if needed)

## Code touchpoints in this repo

- `backend/rag.py` — DualStoreRAG: graph_query, vector_query, build_claude_prompt, suggest_recipes
- `backend/main.py` — POST /profiles/{id}/suggest, history, 7-day context
- `build_graph.py` / `ingest.py` — graph + vector ingestion
- `frontend/.../SuggestionScreen.jsx` — combined + per-person tabs, daily cache

Implement incrementally: retrieval + variety first, then prompt/LLM, then eval harness.
```

---

## What we just shipped (baseline for your next iteration)

| Feature | Status |
|--------|--------|
| 7-day recipe deprioritization | ✅ Graph ranking + Claude prompt |
| Larger candidate pool (40) | ✅ |
| Score-tier shuffle for variety | ✅ |
| Dynamic season by month | ✅ |
| Vector chunk rotation (shuffle pool) | ✅ |
| Daily cache + Regenerate | ✅ Frontend + history |

## Suggested next session

1. Pass **full ingredients** from Neo4j into the Claude prompt (remove 350-char truncation for top picks)
2. Add **MMR** to vector retrieval
3. Store **wisdom chunk IDs** in suggestion history for chunk rotation
4. Score **excess vs deficiency** differently in `_score_recipes`
5. Add **eval script** with 5 fixture tables

---

*Generated for FoodPorn / Rasa Ayurveda — dual-store graph + vector + Claude pipeline.*
