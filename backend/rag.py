"""
Dual-store RAG system combining Neo4j graph queries and Qdrant vector search.
Mirrors the OSSAgent legal RAG pattern for Ayurvedic recipe recommendation.
"""

import os
from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from sentence_transformers import SentenceTransformer
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
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Current season (could be made dynamic based on date)
CURRENT_SEASON = "Summer"  # TODO: Make this dynamic based on datetime


class DualStoreRAG:
    """
    Dual-store RAG system for Ayurvedic recipe recommendations.
    Combines structured graph reasoning with semantic vector search.
    """

    def __init__(self):
        self.neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    def close(self):
        """Close database connections."""
        self.neo4j_driver.close()

    def graph_query(self, people: List[Dict]) -> List[Dict]:
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
                if dosha_assignment.get('is_primary'):
                    must_balance.add(dosha_assignment['dosha'])
                    avoid_aggravating.add(dosha_assignment['dosha'])

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
                LIMIT 30
                """,
                must_balance=list(must_balance),
                avoid_aggravating=list(avoid_aggravating)
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

        # Score and rank recipes
        scored_recipes = self._score_recipes(recipes, people)

        # Return top 15
        return scored_recipes[:15]

    def _score_recipes(self, recipes: List[Dict], people: List[Dict]) -> List[Dict]:
        """
        Score recipes based on how well they match people's needs.
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

                # Get primary and secondary doshas
                primary_doshas = [d['dosha'] for d in person.get('doshas', []) if d.get('is_primary')]
                secondary_doshas = [d['dosha'] for d in person.get('doshas', []) if not d.get('is_primary')]

                # +3 for balancing primary dosha
                for dosha in primary_doshas:
                    if dosha in recipe['balances_doshas']:
                        person_score += 3
                        reasons.append(f"Balances primary {dosha}")

                # +1 for balancing secondary dosha
                for dosha in secondary_doshas:
                    if dosha in recipe['balances_doshas']:
                        person_score += 1
                        reasons.append(f"Balances secondary {dosha}")

                # -5 if aggravates primary dosha (safety net)
                for dosha in primary_doshas:
                    if dosha in recipe['aggravates_doshas']:
                        person_score -= 5
                        reasons.append(f"⚠️ Aggravates primary {dosha}")

                # +2 for each imbalance it helps
                person_imbalances = person.get('imbalances', [])
                for imbalance in person_imbalances:
                    if imbalance in recipe['helps_imbalances']:
                        person_score += 2
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
            if CURRENT_SEASON in recipe['seasons'] or 'All' in recipe['seasons']:
                score += 2

            recipe['score'] = score
            recipe['per_person_reasoning'] = per_person_reasoning
            scored.append(recipe)

        # Sort by score descending
        scored.sort(key=lambda r: r['score'], reverse=True)
        return scored

    def vector_query(self, people: List[Dict], top_k: int = 5) -> List[Dict]:
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

        # Build query string from people's profiles
        dosha_names = set()
        imbalance_names = set()

        for person in people:
            for dosha_assignment in person.get('doshas', []):
                dosha_names.add(dosha_assignment['dosha'])
            for imbalance in person.get('imbalances', []):
                imbalance_names.add(imbalance)

        # Create semantic query
        query_parts = []
        if dosha_names:
            query_parts.append(f"Ayurvedic diet for {', '.join(dosha_names)} dosha")
        if imbalance_names:
            query_parts.append(f"Managing {', '.join(imbalance_names)}")
        query_parts.append("Foods that balance and nourish")

        query_text = ". ".join(query_parts)

        # Embed query
        query_vector = self.embedding_model.encode(query_text).tolist()

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

        # Search Qdrant
        search_result = self.qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=dosha_filter,
            limit=top_k,
            score_threshold=0.3
        )

        # Format results
        chunks = []
        for hit in search_result:
            chunks.append({
                'chunk_id': hit.payload['chunk_id'],
                'source': hit.payload['source'],
                'text': hit.payload['text'],
                'doshas': hit.payload.get('doshas', []),
                'score': hit.score,
                'type': hit.payload.get('type', 'theory')
            })

        return chunks

    def build_claude_prompt(
        self,
        people: List[Dict],
        graph_results: List[Dict],
        vector_results: List[Dict]
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
        for person in people:
            primary_doshas = [d['dosha'] for d in person.get('doshas', []) if d.get('is_primary')]
            secondary_doshas = [d['dosha'] for d in person.get('doshas', []) if not d.get('is_primary')]

            people_section += f"**{person['name']}**\n"
            if primary_doshas:
                people_section += f"- Primary dosha: {', '.join(primary_doshas)}\n"
            if secondary_doshas:
                people_section += f"- Secondary dosha: {', '.join(secondary_doshas)}\n"
            if person.get('imbalances'):
                people_section += f"- Imbalances: {', '.join(person['imbalances'])}\n"
            people_section += f"- Serving count: {person.get('serving_count', 1)}\n\n"

        # Build graph recipes section
        recipes_section = "## Pre-selected recipes from our Ayurvedic knowledge graph\n\n"
        recipes_section += "The following recipes were selected by graph traversal — they structurally balance the doshas present. Each has a score and reasoning:\n\n"

        for i, recipe in enumerate(graph_results, 1):
            recipes_section += f"### {i}. {recipe['name']} (score: {recipe['score']})\n"
            recipes_section += f"**Source:** {recipe['source_book']}\n\n"

            # Why selected
            recipes_section += "**Why selected:**\n"
            for person_name, reasoning in recipe['per_person_reasoning'].items():
                if reasoning['reasons']:
                    recipes_section += f"- {person_name}: {', '.join(reasoning['reasons'])}\n"

            # Properties
            recipes_section += f"\n**Meal type:** {recipe['meal_type'] or 'Not specified'}\n"
            if recipe['qualities']:
                recipes_section += f"**Qualities:** {', '.join(recipe['qualities'])}\n"
            if recipe['tastes']:
                recipes_section += f"**Tastes:** {', '.join(recipe['tastes'])}\n"
            if recipe['helps_imbalances']:
                recipes_section += f"**Helps with:** {', '.join(recipe['helps_imbalances'])}\n"

            # Full recipe text (truncate if very long)
            recipe_text = recipe['raw_text'][:3000]
            if len(recipe['raw_text']) > 3000:
                recipe_text += "\n... (recipe continues)"

            recipes_section += f"\n**Full recipe:**\n{recipe_text}\n\n"
            recipes_section += "---\n\n"

        # Build vector chunks section
        wisdom_section = "## Relevant Ayurvedic wisdom\n\n"
        for i, chunk in enumerate(vector_results, 1):
            wisdom_section += f"**{i}. From {chunk['source']}** (relevance: {chunk['score']:.2f})\n"
            wisdom_section += f"{chunk['text']}\n\n"

        # Build task section
        task_section = f"""## Your task

From the recipes above, select the **6-8 best ones** for today, considering:
- Variety across meal types (don't pick 3 breakfasts)
- Complementary tastes and qualities across the day
- Each person's specific imbalances
- Seasonal appropriateness (current season: {CURRENT_SEASON})

For each selected recipe, write a warm, personal explanation using the people's names.
Be specific about WHY this recipe is right for THIS combination of people today.

Respond ONLY in this JSON format:
{{
  "recipes": [
    {{
      "name": "string",
      "source": "string",
      "overall_fit": "Ideal|Good|Works",
      "why_it_works": "string — warm, personal, uses names",
      "best_for": "string — which person benefits most and why",
      "substitutions": "string or null",
      "per_person": [
        {{"name": "string", "fit": "Ideal|Good|Works", "note": "string"}}
      ]
    }}
  ],
  "meal_harmony_note": "string — how these recipes work together as a day of eating"
}}"""

        # Combine all sections
        prompt = f"{people_section}\n{recipes_section}\n{wisdom_section}\n{task_section}"
        return prompt

    def call_claude(self, prompt: str) -> Dict[str, Any]:
        """
        Call Claude API with the final prompt.

        Args:
            prompt: The complete prompt

        Returns:
            Parsed JSON response from Claude
        """
        system_prompt = """You are an expert Ayurvedic nutritionist with deep knowledge of dosha balancing.
You give warm, specific, personalized advice grounded in traditional principles.
You know these people well and speak to them directly by name."""

        message = self.anthropic.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            temperature=0.7,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse JSON response
        response_text = message.content[0].text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            # Remove trailing ```
            if response_text.endswith('```'):
                response_text = response_text[:-3]

        import json
        return json.loads(response_text.strip())

    def suggest_recipes(self, people: List[Dict]) -> Dict[str, Any]:
        """
        Complete dual-store RAG pipeline for recipe suggestions.

        Args:
            people: List of people dicts

        Returns:
            Dict with recipes, metadata, and source counts
        """
        # Step 1: Query graph
        graph_results = self.graph_query(people)

        # Step 2: Query vectors
        vector_results = self.vector_query(people, top_k=5)

        # Step 3: Build prompt
        prompt = self.build_claude_prompt(people, graph_results, vector_results)

        # Step 4: Call Claude
        claude_response = self.call_claude(prompt)

        # Step 5: Add metadata
        return {
            'recipes': claude_response.get('recipes', []),
            'meal_harmony_note': claude_response.get('meal_harmony_note', ''),
            'graph_recipe_count': len(graph_results),
            'vector_chunk_count': len(vector_results),
            'suggested_at': datetime.utcnow().isoformat()
        }
