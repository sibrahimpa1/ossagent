"""
Dual-store RAG system combining Neo4j graph queries and Qdrant vector search.
Mirrors the OSSAgent legal RAG pattern for Ayurvedic recipe recommendation.
"""

import json
import os
import re
import random
import numpy as np
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from sentence_transformers import SentenceTransformer
import httpx
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "ayurveda123")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

COLLECTION_NAME = "ayurveda_theory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SUGGESTION_MODEL = os.getenv("SUGGESTION_MODEL", "claude-sonnet-4-6")
SUGGESTION_MAX_TOKENS = int(os.getenv("SUGGESTION_MAX_TOKENS", "8192"))


def create_anthropic_client() -> Anthropic:
    """Build Anthropic client with explicit httpx — avoids proxies/httpx version conflicts."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return Anthropic(
        api_key=ANTHROPIC_API_KEY,
        http_client=httpx.Client(timeout=120.0),
    )


def _format_dosha_with_tendency(dosha: str, tendency: Optional[str]) -> str:
    if tendency == "excess":
        return f"{dosha} (in excess)"
    if tendency == "deficiency":
        return f"{dosha} (deficient)"
    return dosha


def normalize_person_doshas(doshas: List[Dict]) -> List[Dict]:
    """Collapse duplicate dosha rows from DB into unique primary/imbalance lists."""
    primary = []
    secondary = []
    seen_primary = set()
    seen_secondary = set()
    for item in doshas:
        name = item.get("dosha")
        if not name:
            continue
        tendency = item.get("tendency")
        if item.get("is_primary"):
            if name not in seen_primary:
                seen_primary.add(name)
                primary.append({"dosha": name, "is_primary": True, "tendency": tendency})
        elif name not in seen_secondary:
            seen_secondary.add(name)
            secondary.append({"dosha": name, "is_primary": False, "tendency": tendency})
    return primary + secondary

# Current season (dynamic by month in northern hemisphere)
def get_current_season(reference: Optional[datetime] = None) -> str:
    month = (reference or datetime.utcnow()).month
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Fall"


CURRENT_SEASON = get_current_season()  # module load default; call get_current_season() at runtime in prompts


def extract_recipe_names_from_suggestion(response: Dict[str, Any]) -> List[str]:
    """Collect unique recipe names from a suggestion payload (combined + individual)."""
    names: List[str] = []
    seen: Set[str] = set()

    combined = (response.get("combined") or {}).get("recipes") or response.get("recipes") or []
    for recipe in combined:
        name = recipe.get("name") if isinstance(recipe, dict) else None
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    for section in response.get("individual") or []:
        for recipe in section.get("recipes") or []:
            name = recipe.get("name") if isinstance(recipe, dict) else None
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    return names


class DualStoreRAG:
    """
    Dual-store RAG system for Ayurvedic recipe recommendations.
    Combines structured graph reasoning with semantic vector search.
    """

    def __init__(self):
        self.neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._embedding_model = None
        self._anthropic = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedding_model

    @property
    def anthropic(self):
        if self._anthropic is None:
            self._anthropic = create_anthropic_client()
        return self._anthropic

    def close(self):
        """Close database connections."""
        self.neo4j_driver.close()

    def graph_query(
        self,
        people: List[Dict],
        *,
        exclude_names: Optional[Set[str]] = None,
        candidate_count: int = 8,
        pool_limit: int = 40,
    ) -> List[Dict]:
        """
        Query Neo4j for recipes that match people's dosha profiles.

        Args:
            people: List of dicts with keys: name, doshas (list of {dosha, is_primary}), imbalances (list of str)

        Returns:
            List of recipe dicts with scores and reasoning
        """
        if not people:
            return []

        # Build sets from all people
        must_balance = set()
        avoid_aggravating = set()
        all_imbalances = set()

        for person in people:
            for dosha_assignment in person.get('doshas', []):
                dosha = dosha_assignment['dosha']
                must_balance.add(dosha)
                if dosha_assignment.get('is_primary'):
                    avoid_aggravating.add(dosha)
                else:
                    # Secondary / imbalance dosha — still needs balancing, softer aggravation rule
                    avoid_aggravating.add(dosha)

            for imbalance in person.get('imbalances', []):
                all_imbalances.add(imbalance)

        # Run Cypher query
        with self.neo4j_driver.session() as session:
            # Find recipes that balance all primary doshas and don't aggravate any
            result = session.run(
                """
                MATCH (r:Recipe)
                WHERE ALL(d IN $must_balance WHERE EXISTS {
                    MATCH (r)-[:BALANCES]->(:Dosha {name: d})
                })
                AND NOT ANY(d IN $avoid_aggravating WHERE EXISTS {
                    MATCH (r)-[:AGGRAVATES]->(:Dosha {name: d})
                })

                OPTIONAL MATCH (r)-[:BALANCES]->(balanced_dosha:Dosha)
                OPTIONAL MATCH (r)-[:AGGRAVATES]->(aggravated_dosha:Dosha)
                OPTIONAL MATCH (r)-[:HELPS_WITH]->(i:Imbalance)
                OPTIONAL MATCH (r)-[:HAS_QUALITY]->(q:Quality)
                OPTIONAL MATCH (r)-[:HAS_TASTE]->(t:Taste)
                OPTIONAL MATCH (r)-[:MEAL_TYPE]->(m:MealType)
                OPTIONAL MATCH (r)-[:SUITS_SEASON]->(s:Season)

                RETURN r,
                       collect(DISTINCT balanced_dosha.name) as balances_doshas,
                       collect(DISTINCT aggravated_dosha.name) as aggravates_doshas,
                       collect(DISTINCT i.name) as helps_imbalances,
                       collect(DISTINCT q.name) as qualities,
                       collect(DISTINCT t.name) as tastes,
                       collect(DISTINCT m.name) as meal_types,
                       collect(DISTINCT s.name) as seasons
                LIMIT $pool_limit
                """,
                must_balance=list(must_balance),
                avoid_aggravating=list(avoid_aggravating),
                pool_limit=pool_limit,
            )

            recipes = []
            for record in result:
                recipe_node = record['r']
                recipe_data = {
                    'name': recipe_node['name'],
                    'source_book': recipe_node.get('source_book', 'Unknown'),
                    'meal_type': recipe_node.get('meal_type'),
                    'prep_time_minutes': recipe_node.get('prep_time_minutes'),
                    'serves': recipe_node.get('serves'),
                    'raw_text': recipe_node.get('raw_text', ''),
                    'notes': recipe_node.get('notes'),
                    'balances_doshas': record['balances_doshas'],
                    'aggravates_doshas': record['aggravates_doshas'],
                    'helps_imbalances': record['helps_imbalances'],
                    'qualities': record['qualities'],
                    'tastes': record['tastes'],
                    'meal_types': record['meal_types'],
                    'seasons': record['seasons']
                }
                recipes.append(recipe_data)

        # Score and rank recipes, preferring names not seen recently
        scored_recipes = self._score_recipes(recipes, people)
        exclude = exclude_names or set()
        return self._select_diverse_candidates(scored_recipes, exclude, candidate_count)

    def _shuffle_score_tiers(self, recipes: List[Dict]) -> List[Dict]:
        """Shuffle within equal score bands so tie-breaks vary between runs."""
        if not recipes:
            return []
        shuffled: List[Dict] = []
        index = 0
        while index < len(recipes):
            score = recipes[index]["score"]
            tier: List[Dict] = []
            while index < len(recipes) and recipes[index]["score"] == score:
                tier.append(recipes[index])
                index += 1
            random.shuffle(tier)
            shuffled.extend(tier)
        return shuffled

    def _select_diverse_candidates(
        self,
        scored: List[Dict],
        exclude_names: Set[str],
        count: int,
    ) -> List[Dict]:
        fresh = self._shuffle_score_tiers([r for r in scored if r["name"] not in exclude_names])
        stale = self._shuffle_score_tiers([r for r in scored if r["name"] in exclude_names])
        selected = fresh[:count]
        if len(selected) < count:
            selected.extend(stale[: count - len(selected)])
        return selected

    def _score_recipes(self, recipes: List[Dict], people: List[Dict]) -> List[Dict]:
        """
        Score recipes based on how well they match people's needs.
        Differentiates between excess vs deficiency tendencies.
        Adds diversity bonus for meal type variety.
        """
        scored = []
        meal_types_covered = set()

        for recipe in recipes:
            score = 0
            per_person_reasoning = {}

            # Score for each person
            for person in people:
                person_score = 0
                reasons = []

                # Get dosha assignments with tendency info
                primary_doshas = {}  # {dosha_name: tendency}
                secondary_doshas = {}

                for d in person.get('doshas', []):
                    dosha_name = d['dosha']
                    tendency = d.get('tendency')  # 'excess', 'deficiency', or None
                    if d.get('is_primary'):
                        primary_doshas[dosha_name] = tendency
                    else:
                        secondary_doshas[dosha_name] = tendency

                # Score primary doshas with tendency awareness
                for dosha, tendency in primary_doshas.items():
                    if dosha in recipe['balances_doshas']:
                        if tendency == 'excess':
                            # Excess dosha needs strong pacifying
                            person_score += 4  # +1 bonus for excess
                            reasons.append(f"Pacifies excess {dosha}")
                        elif tendency == 'deficiency':
                            # Deficient dosha needs gentler building support
                            person_score += 2  # Lower score, needs building not balancing
                            reasons.append(f"Supports deficient {dosha}")
                        else:
                            # Normal primary dosha balance
                            person_score += 3
                            reasons.append(f"Balances primary {dosha}")

                    # Aggravation penalties (stronger for excess tendency)
                    if dosha in recipe['aggravates_doshas']:
                        if tendency == 'excess':
                            person_score -= 7  # Worse to aggravate excess
                            reasons.append(f"⚠️ Aggravates excess {dosha}")
                        else:
                            person_score -= 5
                            reasons.append(f"⚠️ Aggravates primary {dosha}")

                # Score secondary/imbalance doshas
                for dosha, tendency in secondary_doshas.items():
                    if dosha in recipe['balances_doshas']:
                        # Imbalance doshas typically in excess
                        if tendency == 'excess' or tendency is None:
                            person_score += 2  # Good to balance imbalance
                            reasons.append(f"Balances imbalance {dosha}")
                        elif tendency == 'deficiency':
                            person_score += 1
                            reasons.append(f"Supports {dosha}")

                # +3 for each named imbalance it helps (higher priority than before)
                person_imbalances = person.get('imbalances', [])
                for imbalance in person_imbalances:
                    if imbalance in recipe['helps_imbalances']:
                        person_score += 3  # Increased from +2
                        reasons.append(f"Helps with {imbalance}")

                score += person_score
                per_person_reasoning[person['name']] = {
                    'score': person_score,
                    'reasons': reasons
                }

            # Diversity bonus: +1 if meal type not yet covered
            meal_type = recipe['meal_type']
            if meal_type and meal_type not in meal_types_covered:
                score += 1
                meal_types_covered.add(meal_type)

            # Season bonus: +2 if suitable for current season or "All"
            season = get_current_season()
            if season in recipe['seasons'] or 'All' in recipe['seasons']:
                score += 2

            recipe['score'] = score
            recipe['per_person_reasoning'] = per_person_reasoning
            scored.append(recipe)

        # Sort by score descending
        scored.sort(key=lambda r: r['score'], reverse=True)
        return scored

    def _mmr_select(
        self,
        candidates: List[Dict],
        query_embedding: np.ndarray,
        top_k: int,
        lambda_param: float = 0.6
    ) -> List[Dict]:
        """
        Maximal Marginal Relevance selection for diverse results.

        Args:
            candidates: List of candidate chunks with embeddings
            query_embedding: Query embedding vector
            top_k: Number of chunks to select
            lambda_param: Balance between relevance (1.0) and diversity (0.0)

        Returns:
            Diversified list of chunks
        """
        if not candidates or top_k <= 0:
            return []

        if len(candidates) <= top_k:
            return candidates

        # Normalize query embedding
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)

        # Extract embeddings and compute relevance scores
        embeddings = []
        for cand in candidates:
            emb = np.array(cand.get('embedding', []))
            if len(emb) == 0:
                # Fallback: re-embed the text if embedding not stored
                emb = self.embedding_model.encode(cand['text'])
                cand['embedding'] = emb.tolist()
            embeddings.append(emb)

        embeddings = np.array(embeddings)

        # Normalize all embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        embeddings_norm = embeddings / norms

        # Compute relevance scores (cosine similarity with query)
        relevance_scores = np.dot(embeddings_norm, query_norm)

        selected_indices = []
        selected_embeddings = []

        for _ in range(min(top_k, len(candidates))):
            if not selected_indices:
                # First selection: most relevant
                best_idx = np.argmax(relevance_scores)
            else:
                # MMR: balance relevance vs diversity
                mmr_scores = []
                for idx in range(len(candidates)):
                    if idx in selected_indices:
                        mmr_scores.append(-np.inf)
                        continue

                    # Relevance component
                    relevance = relevance_scores[idx]

                    # Diversity component (max similarity to already selected)
                    similarities = np.dot(embeddings_norm[idx], np.array(selected_embeddings).T)
                    max_sim = np.max(similarities) if len(similarities) > 0 else 0

                    # MMR score
                    mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
                    mmr_scores.append(mmr)

                best_idx = np.argmax(mmr_scores)

            selected_indices.append(best_idx)
            selected_embeddings.append(embeddings_norm[best_idx])

        return [candidates[idx] for idx in selected_indices]

    def vector_query(
        self,
        people: List[Dict],
        top_k: int = 5,
        *,
        exclude_chunk_ids: Optional[Set[str]] = None,
    ) -> List[Dict]:
        """
        Query Qdrant for relevant Ayurvedic theory chunks.

        Args:
            people: List of people dicts
            top_k: Number of chunks to return

        Returns:
            List of theory chunks with scores
        """
        if not people:
            return []

        # Build query strings from people's profiles
        dosha_names = set()
        imbalance_names = set()

        for person in people:
            for dosha_assignment in person.get('doshas', []):
                dosha_names.add(dosha_assignment['dosha'])
            for imbalance in person.get('imbalances', []):
                imbalance_names.add(imbalance)

        # Build filter: doshas overlap with people's doshas
        dosha_filter = None
        if dosha_names:
            dosha_filter = Filter(
                should=[
                    FieldCondition(
                        key="doshas",
                        match=MatchAny(any=[d.lower() for d in dosha_names])
                    )
                ]
            )

        # Create multiple queries: general dosha query + one per imbalance
        queries = []

        # General dosha query
        general_parts = []
        if dosha_names:
            general_parts.append(f"Ayurvedic diet for {', '.join(dosha_names)} dosha")
        general_parts.append("Foods that balance and nourish")
        queries.append(". ".join(general_parts))

        # Separate query for each named imbalance
        for imbalance in imbalance_names:
            queries.append(f"Managing {imbalance} with Ayurvedic diet and nutrition")

        # Search Qdrant with multiple queries and merge results
        candidates_map = {}  # chunk_id -> candidate dict (deduplication)
        exclude_ids = exclude_chunk_ids or set()

        # Fetch candidates per query
        fetch_limit_per_query = max((top_k * 4) // len(queries), 8) if queries else 16

        # Store first query embedding for MMR (general dosha query)
        reference_query_embedding = None

        for i, query_text in enumerate(queries):
            query_embedding = self.embedding_model.encode(query_text)
            query_vector = query_embedding.tolist()

            # Use first query as reference for MMR
            if i == 0:
                reference_query_embedding = query_embedding

            search_result = self.qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=dosha_filter,
                limit=fetch_limit_per_query,
                score_threshold=0.3,
                with_vectors=True  # Get embeddings for MMR
            ).points

            # Merge candidates (keep highest score if duplicate)
            for hit in search_result:
                chunk_id = hit.payload['chunk_id']
                if chunk_id in exclude_ids:
                    continue

                # Store embedding for MMR
                embedding = hit.vector if hasattr(hit, 'vector') else None
                if embedding is None:
                    # Fallback: re-embed if not returned
                    embedding = self.embedding_model.encode(hit.payload['text']).tolist()

                candidate = {
                    'chunk_id': chunk_id,
                    'source': hit.payload['source'],
                    'text': hit.payload['text'],
                    'doshas': hit.payload.get('doshas', []),
                    'score': hit.score,
                    'type': hit.payload.get('type', 'theory'),
                    'embedding': embedding
                }

                # Keep highest score if already exists
                if chunk_id not in candidates_map or hit.score > candidates_map[chunk_id]['score']:
                    candidates_map[chunk_id] = candidate

        candidates = list(candidates_map.values())

        # Apply MMR for diversity using the general query embedding
        if len(candidates) > top_k and reference_query_embedding is not None:
            chunks = self._mmr_select(candidates, reference_query_embedding, top_k, lambda_param=0.6)
        else:
            chunks = candidates

        # Remove embeddings from final output (save tokens in prompts)
        for chunk in chunks:
            chunk.pop('embedding', None)

        return chunks[:top_k]

    def _append_graph_recipes_section(
        self,
        section: str,
        graph_results: List[Dict],
        *,
        heading: str,
        intro: str = "",
        top_candidates: int = 5,
    ) -> str:
        """
        Add graph recipe candidates to prompt.

        Args:
            top_candidates: Number of top recipes to include FULL text for (default 5)
        """
        section += f"## {heading}\n\n"
        if intro:
            section += f"{intro}\n\n"
        if not graph_results:
            section += "_No strong graph matches found — use Ayurvedic principles from wisdom below._\n\n"
            return section

        for i, recipe in enumerate(graph_results, 1):
            section += f"### {i}. {recipe['name']} (score: {recipe.get('score', 0)})\n"
            section += f"**Source:** {recipe['source_book']}\n\n"
            section += "**Why selected:**\n"
            for person_name, reasoning in recipe.get('per_person_reasoning', {}).items():
                if reasoning.get('reasons'):
                    section += f"- {person_name}: {', '.join(reasoning['reasons'])}\n"
            section += f"\n**Meal type:** {recipe.get('meal_type') or 'Not specified'}\n"
            if recipe.get('qualities'):
                section += f"**Qualities:** {', '.join(recipe['qualities'])}\n"
            if recipe.get('tastes'):
                section += f"**Tastes:** {', '.join(recipe['tastes'])}\n"
            if recipe.get('helps_imbalances'):
                section += f"**Helps with:** {', '.join(recipe['helps_imbalances'])}\n"

            # Pass FULL recipe text for top candidates, truncate the rest
            raw_text = recipe.get('raw_text') or ''
            if i <= top_candidates:
                # Top candidates get full text for better ingredient extraction
                recipe_text = raw_text
            else:
                # Lower-ranked candidates get truncated to save tokens
                recipe_text = raw_text[:350]
                if len(raw_text) > 350:
                    recipe_text += "..."

            if recipe_text:
                section += f"\n**Recipe details:**\n{recipe_text}\n\n"
            section += "---\n\n"
        return section

    def build_claude_prompt(
        self,
        people: List[Dict],
        graph_results: List[Dict],
        vector_results: List[Dict],
        individual_graph: Optional[Dict[str, List[Dict]]] = None,
        recent_recipe_names: Optional[List[str]] = None,
    ) -> str:
        """
        Build the final prompt for Claude combining graph and vector results.

        Args:
            people: List of people dicts
            graph_results: Top recipes from Neo4j
            vector_results: Top theory chunks from Qdrant

        Returns:
            Formatted prompt string
        """
        # Build people section
        people_section = "## People cooking today\n\n"
        people_section += f"**Table size:** {len(people)} {'person' if len(people) == 1 else 'people'} cooking (scale recipes for the group)\n\n"
        for person in people:
            primary_entries = [d for d in person.get('doshas', []) if d.get('is_primary')]
            secondary_entries = [d for d in person.get('doshas', []) if not d.get('is_primary')]
            primary_labels = list(dict.fromkeys(
                _format_dosha_with_tendency(d['dosha'], d.get('tendency')) for d in primary_entries
            ))
            secondary_labels = list(dict.fromkeys(
                _format_dosha_with_tendency(d['dosha'], d.get('tendency')) for d in secondary_entries
            ))

            people_section += f"**{person['name']}**\n"
            if primary_labels:
                people_section += f"- Primary dosha: {', '.join(primary_labels)}\n"
            if secondary_labels:
                people_section += f"- Imbalance dosha: {', '.join(secondary_labels)}\n"
            if person.get('imbalances'):
                people_section += f"- Imbalances: {', '.join(person['imbalances'])}\n"
            people_section += "\n"

        recipes_section = ""
        recipes_section = self._append_graph_recipes_section(
            recipes_section,
            graph_results,
            heading="Combined table — graph recipe picks",
            intro="Recipes that balance everyone cooking together at one shared meal.",
        )

        if individual_graph:
            for person_name, person_results in individual_graph.items():
                recipes_section = self._append_graph_recipes_section(
                    recipes_section,
                    person_results,
                    heading=f"Solo meal picks for {person_name}",
                    intro=f"Recipes suited when cooking just for {person_name}, separate from the group meal.",
                )

        # Build vector chunks section
        wisdom_section = "## Relevant Ayurvedic wisdom\n\n"
        for i, chunk in enumerate(vector_results, 1):
            wisdom_section += f"**{i}. From {chunk['source']}** (relevance: {chunk['score']:.2f})\n"
            wisdom_section += f"{chunk['text']}\n\n"

        season = get_current_season()
        variety_section = ""
        if recent_recipe_names:
            variety_section = "## Variety — avoid recent repeats\n\n"
            variety_section += (
                "These recipes were already suggested for this table in the **last 7 days**. "
                "Prefer **different** recipes from the graph picks above. "
                "Only repeat one if there is no reasonable alternative.\n\n"
            )
            for name in recent_recipe_names[:30]:
                variety_section += f"- {name}\n"
            variety_section += "\n"

        recipe_schema = """
      "name": "string",
      "source": "string",
      "overall_fit": "Ideal|Good|Works",
      "why_it_works": "string",
      "best_for": "string",
      "substitutions": "string or null",
      "ingredients": ["string"],
      "per_person": [
        {{"name": "string", "fit": "Ideal|Good|Works", "note": "string"}}
      ]"""

        if len(people) > 1:
            task_section = f"""## Your task

Provide recipe suggestions in **two sections**:

1. **combined** — {len(people)} people eating **one shared meal** together today. Pick **3 recipes** that work for the whole table (include per_person breakdown for each).
2. **individual** — separate meals if each person cooks **their own dish**. For each person, pick **2 recipes** tailored only to them (per_person can be just that one person).

IMPORTANT CONSTRAINTS:
- You MUST select recipes ONLY from the graph candidate sections above
- Each recipe "name" must exactly match a name from the graph candidates
- Use the "Source" book name from the graph candidates, not made-up sources
- Extract ingredients from the "Recipe details" in the graph candidates
- Prefer recipes with higher scores and variety in meal types
- Consider variety, imbalances, and season ({season}). Keep notes to 1-2 sentences. No markdown.
- Pick recipes **not** in the recent-repeat list unless necessary.

Respond ONLY with valid JSON:
{{
  "combined": {{
    "meal_harmony_note": "string — how these shared recipes work together",
    "recipes": [
      {{ {recipe_schema} }}
    ]
  }},
  "individual": [
    {{
      "person_name": "string",
      "meal_note": "string — brief note for this person's solo meals",
      "recipes": [
        {{ {recipe_schema} }}
      ]
    }}
  ]
}}"""
        else:
            task_section = f"""## Your task

Pick **3 recipes** for today for this one person.

IMPORTANT CONSTRAINTS:
- You MUST select recipes ONLY from the graph candidate sections above
- Each recipe "name" must exactly match a name from the graph candidates
- Use the "Source" book name from the graph candidates, not made-up sources
- Extract ingredients from the "Recipe details" in the graph candidates
- Consider variety, imbalances, and season ({season})
- Pick recipes **not** in the recent-repeat list unless necessary

Respond ONLY with valid JSON:
{{
  "combined": {{
    "meal_harmony_note": "string",
    "recipes": [
      {{ {recipe_schema} }}
    ]
  }},
  "individual": []
}}"""

        # Combine all sections
        prompt = f"{people_section}\n{recipes_section}\n{wisdom_section}\n{variety_section}\n{task_section}"
        return prompt

    def _extract_json_text(self, response_text: str) -> str:
        text = response_text.strip()
        if text.startswith('```'):
            parts = text.split('```')
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith('json'):
                    text = text[4:]
        text = text.strip()
        if text.endswith('```'):
            text = text[:-3].strip()
        return text

    def _parse_claude_json(self, response_text: str) -> Dict[str, Any]:
        text = self._extract_json_text(response_text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
            raise

    def _recipes_from_graph(self, graph_results: List[Dict], *, best_for: str = 'Everyone at the table') -> List[Dict]:
        recipes = []
        for recipe in graph_results:
            name = recipe.get('name', 'Recipe')
            recipes.append({
                'name': name,
                'source': recipe.get('source_book') or 'Ayurvedic knowledge graph',
                'overall_fit': 'Good',
                'why_it_works': f'{name} balances the doshas based on our recipe graph.',
                'best_for': best_for,
                'substitutions': None,
                'ingredients': [],
                'per_person': [],
            })
        return recipes

    def _normalize_suggestion_response(self, raw: Dict[str, Any], people: List[Dict]) -> Dict[str, Any]:
        if 'combined' in raw:
            combined = raw.get('combined') or {}
            individual = raw.get('individual') or []
        else:
            combined = {
                'meal_harmony_note': raw.get('meal_harmony_note', ''),
                'recipes': raw.get('recipes', []),
            }
            individual = []

        combined_recipes = combined.get('recipes') or []
        combined_note = combined.get('meal_harmony_note') or ''

        return {
            'combined': {
                'meal_harmony_note': combined_note,
                'recipes': combined_recipes,
            },
            'individual': individual,
            'recipes': combined_recipes,
            'meal_harmony_note': combined_note,
        }

    def _fallback_from_graph(
        self,
        graph_results: List[Dict],
        people: Optional[List[Dict]] = None,
        *,
        exclude_names: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        exclude = exclude_names or set()
        fresh = [r for r in graph_results if r.get('name') not in exclude]
        pool = fresh if len(fresh) >= 3 else graph_results
        combined_recipes = self._recipes_from_graph(pool[:3])
        combined = {
            'meal_harmony_note': 'These graph-selected recipes work together for balanced eating today.',
            'recipes': combined_recipes,
        }
        individual = []
        if people and len(people) > 1:
            for person in people:
                person_graph = self.graph_query([person], exclude_names=exclude, candidate_count=4)
                individual.append({
                    'person_name': person['name'],
                    'meal_note': f"Recipes tailored for {person['name']} when cooking separately.",
                    'recipes': self._recipes_from_graph(
                        person_graph[:2],
                        best_for=person['name'],
                    ),
                })
        return self._normalize_suggestion_response({'combined': combined, 'individual': individual}, people or [])

    def call_claude(self, prompt: str, *, compact: bool = False) -> Dict[str, Any]:
        """
        Call Claude API with the final prompt.

        Args:
            prompt: The complete prompt

        Returns:
            Parsed JSON response from Claude
        """
        system_prompt = """You are an expert Ayurvedic nutritionist with deep knowledge of dosha balancing.
You give warm, specific, personalized advice grounded in traditional principles.
You know these people well and speak to them directly by name.

CRITICAL RULES:
1. You may ONLY recommend recipes from the provided graph candidate list. Never invent or hallucinate recipes.
2. Each recipe name in your response must exactly match a recipe name from the graph candidates.
3. Use the "source" field from the graph candidates - never make up book names.
4. Extract ingredients from the recipe details provided in the graph candidates.
5. Your role is to SELECT and EXPLAIN the best graph candidates, not to create new recipes.
6. When explaining "why_it_works", reference the dosha balancing properties from the graph.
7. You MUST respond with complete, valid JSON only — never truncate mid-string."""

        user_content = prompt
        if compact:
            user_content += "\n\nIMPORTANT: Return valid JSON with combined + individual sections. Keep all notes very short."

        message = self.anthropic.messages.create(
            model=SUGGESTION_MODEL,
            max_tokens=SUGGESTION_MAX_TOKENS,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": user_content
            }]
        )

        response_text = message.content[0].text.strip()

        try:
            return self._parse_claude_json(response_text)
        except json.JSONDecodeError as exc:
            if message.stop_reason == 'max_tokens' or not compact:
                return self.call_claude(prompt, compact=True)
            raise exc

    def suggest_recipes(
        self,
        people: List[Dict],
        *,
        recent_recipe_names: Optional[List[str]] = None,
        recent_wisdom_chunk_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Complete dual-store RAG pipeline for recipe suggestions.

        Args:
            people: List of people dicts
            recent_recipe_names: Recipe names to deprioritize (typically last 7 days)
            recent_wisdom_chunk_ids: Theory chunk IDs already used recently

        Returns:
            Dict with recipes, metadata, and source counts
        """
        exclude_names = set(recent_recipe_names or [])
        exclude_chunks = set(recent_wisdom_chunk_ids or [])

        # Step 1: Query graph (combined + per-person for solo meals)
        # Fetch 40+ candidates for better variety pool before Claude selection
        graph_results = self.graph_query(people, exclude_names=exclude_names, candidate_count=40)
        individual_graph = {}
        if len(people) > 1:
            for person in people:
                individual_graph[person['name']] = self.graph_query(
                    [person],
                    exclude_names=exclude_names,
                    candidate_count=20,
                )

        # Step 2: Query vectors - fetch more wisdom for richer context
        vector_results = self.vector_query(people, top_k=6, exclude_chunk_ids=exclude_chunks)

        # Step 3: Build prompt
        prompt = self.build_claude_prompt(
            people,
            graph_results,
            vector_results,
            individual_graph=individual_graph or None,
            recent_recipe_names=list(exclude_names),
        )

        # Step 4: Call Claude (fallback to graph picks if parsing still fails)
        try:
            claude_response = self.call_claude(prompt)
        except (json.JSONDecodeError, Exception):
            claude_response = self._fallback_from_graph(
                graph_results, people, exclude_names=exclude_names
            )

        normalized = self._normalize_suggestion_response(claude_response, people)

        # Step 5: Add metadata including chunk IDs for rotation
        return {
            **normalized,
            'graph_recipe_count': len(graph_results),
            'vector_chunk_count': len(vector_results),
            'vector_chunk_ids': [chunk['chunk_id'] for chunk in vector_results],
            'suggested_at': datetime.utcnow().isoformat()
        }
