#!/usr/bin/env python3
"""
Build Neo4j knowledge graph from chunks.json using Claude for recipe extraction.
Caches all Claude API calls to avoid re-processing.
"""

import json
import os
import time
from typing import Dict, List, Optional
from pathlib import Path

from neo4j import GraphDatabase
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
CHUNKS_PATH = "data/chunks.json"
CACHE_PATH = "data/graph_extractions.json"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "ayurveda123")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "claude-opus-4-8")

# Batch configuration for Claude API calls
BATCH_SIZE = 5
BATCH_DELAY_SECONDS = 1

# Ontology definitions
DOSHAS = ["Vata", "Pitta", "Kapha"]
TASTES = ["Sweet", "Sour", "Salty", "Pungent", "Bitter", "Astringent"]
QUALITIES = ["Heating", "Cooling", "Heavy", "Light", "Dry", "Oily", "Grounding", "Stimulating"]
SEASONS = ["Spring", "Summer", "Autumn", "Winter", "All"]
MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack", "Drink", "Dessert", "Side", "Condiment"]

# Dosha-Taste relationships (traditional Ayurvedic wisdom)
DOSHA_TASTE_NEEDS = {
    "Vata": ["Sweet", "Sour", "Salty"],
    "Pitta": ["Sweet", "Bitter", "Astringent"],
    "Kapha": ["Pungent", "Bitter", "Astringent"]
}

DOSHA_TASTE_AVOID = {
    "Vata": ["Bitter", "Pungent", "Astringent"],
    "Pitta": ["Sour", "Salty", "Pungent"],
    "Kapha": ["Sweet", "Sour", "Salty"]
}

# Common imbalances per dosha
DOSHA_IMBALANCES = {
    "Vata": ["Anxiety", "Poor-Digestion", "Dry-Skin", "Insomnia", "Joint-Pain", "Constipation"],
    "Pitta": ["Inflammation", "Acid-Reflux", "Skin-Rashes", "Anger", "Excessive-Heat"],
    "Kapha": ["Congestion", "Weight-Gain", "Lethargy", "Depression", "Slow-Digestion", "Mucus"]
}

# Claude extraction prompt
EXTRACTION_PROMPT = """You are an Ayurvedic nutritionist and ontologist.
Extract structured data from this recipe text.
Use the pre-tagged doshas as a strong signal but correct them if the recipe text
clearly contradicts them (e.g. heavy cream in a "Kapha" recipe is suspicious).
Respond ONLY in valid JSON. No markdown, no preamble, no explanation.

Recipe text: {text}
Pre-tagged doshas from book section: {doshas}
Source book: {source}

Extract and return:
{{
  "recipe_name": "string — clean name, no trailing punctuation",
  "meal_type": "Breakfast|Lunch|Dinner|Snack|Drink|Dessert|Side|Condiment",
  "prep_time_minutes": number or null,
  "serves": number or null,
  "balances_doshas": ["vata"|"pitta"|"kapha"],
  "aggravates_doshas": ["vata"|"pitta"|"kapha"],
  "helps_with_imbalances": [
    "one of: Anxiety|Poor-Digestion|Dry-Skin|Insomnia|Joint-Pain|Constipation|Inflammation|Acid-Reflux|Skin-Rashes|Anger|Excessive-Heat|Congestion|Weight-Gain|Lethargy|Depression|Slow-Digestion|Mucus"
  ],
  "ingredients": ["normalized ingredient name, lowercase, no amounts"],
  "tastes": ["Sweet"|"Sour"|"Salty"|"Pungent"|"Bitter"|"Astringent"],
  "qualities": ["Heating"|"Cooling"|"Heavy"|"Light"|"Dry"|"Oily"|"Grounding"|"Stimulating"],
  "suitable_seasons": ["Spring"|"Summer"|"Autumn"|"Winter"|"All"],
  "notes": "any important Ayurvedic note about this recipe or null"
}}"""


class GraphBuilder:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cached Claude extractions if they exist."""
        if Path(CACHE_PATH).exists():
            with open(CACHE_PATH, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save Claude extraction cache."""
        Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Clear all nodes and relationships from Neo4j."""
        print("🗑️  Clearing existing database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("✅ Database cleared")

    def seed_base_nodes(self):
        """Seed fundamental ontology nodes that don't change."""
        print("\n🌱 Seeding base ontology nodes...")

        with self.driver.session() as session:
            # Seed Doshas
            for dosha in DOSHAS:
                session.run("MERGE (:Dosha {name: $name})", name=dosha)
            print(f"   ✓ Seeded {len(DOSHAS)} Dosha nodes")

            # Seed Tastes
            for taste in TASTES:
                session.run("MERGE (:Taste {name: $name})", name=taste)
            print(f"   ✓ Seeded {len(TASTES)} Taste nodes")

            # Seed Qualities
            for quality in QUALITIES:
                session.run("MERGE (:Quality {name: $name})", name=quality)
            print(f"   ✓ Seeded {len(QUALITIES)} Quality nodes")

            # Seed Seasons
            for season in SEASONS:
                session.run("MERGE (:Season {name: $name})", name=season)
            print(f"   ✓ Seeded {len(SEASONS)} Season nodes")

            # Seed MealTypes
            for meal_type in MEAL_TYPES:
                session.run("MERGE (:MealType {name: $name})", name=meal_type)
            print(f"   ✓ Seeded {len(MEAL_TYPES)} MealType nodes")

            # Seed Imbalances
            imbalance_count = 0
            for dosha, imbalances in DOSHA_IMBALANCES.items():
                for imbalance in imbalances:
                    session.run(
                        "MERGE (i:Imbalance {name: $name, dosha: $dosha})",
                        name=imbalance,
                        dosha=dosha
                    )
                    # Link to parent dosha
                    session.run(
                        """
                        MATCH (d:Dosha {name: $dosha})
                        MATCH (i:Imbalance {name: $imbalance})
                        MERGE (d)-[:COMMON_IMBALANCE]->(i)
                        """,
                        dosha=dosha,
                        imbalance=imbalance
                    )
                    imbalance_count += 1
            print(f"   ✓ Seeded {imbalance_count} Imbalance nodes")

    def seed_dosha_taste_relationships(self):
        """Seed traditional Ayurvedic dosha-taste relationships."""
        print("\n🔗 Seeding dosha-taste relationships...")

        with self.driver.session() as session:
            needs_count = 0
            for dosha, tastes in DOSHA_TASTE_NEEDS.items():
                for taste in tastes:
                    session.run(
                        """
                        MATCH (d:Dosha {name: $dosha})
                        MATCH (t:Taste {name: $taste})
                        MERGE (d)-[:NEEDS_TASTE]->(t)
                        """,
                        dosha=dosha,
                        taste=taste
                    )
                    needs_count += 1
            print(f"   ✓ Created {needs_count} NEEDS_TASTE relationships")

            avoid_count = 0
            for dosha, tastes in DOSHA_TASTE_AVOID.items():
                for taste in tastes:
                    session.run(
                        """
                        MATCH (d:Dosha {name: $dosha})
                        MATCH (t:Taste {name: $taste})
                        MERGE (d)-[:AVOID_TASTE]->(t)
                        """,
                        dosha=dosha,
                        taste=taste
                    )
                    avoid_count += 1
            print(f"   ✓ Created {avoid_count} AVOID_TASTE relationships")

    def extract_recipe_with_claude(self, chunk: Dict) -> Optional[Dict]:
        """Extract structured recipe data using Claude API."""
        chunk_id = str(chunk['id'])

        # Check cache first
        if chunk_id in self.cache:
            return self.cache[chunk_id]

        # Build prompt
        prompt = EXTRACTION_PROMPT.format(
            text=chunk['text'][:4000],  # Truncate very long recipes
            doshas=chunk.get('doshas', []),
            source=chunk.get('source', 'Unknown')
        )

        try:
            # Call Claude API
            message = self.anthropic.messages.create(
                model=EXTRACTION_MODEL,
                max_tokens=2000,
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

            extraction = json.loads(response_text)

            # Normalize dosha names to title case
            extraction['balances_doshas'] = [d.capitalize() for d in extraction.get('balances_doshas', [])]
            extraction['aggravates_doshas'] = [d.capitalize() for d in extraction.get('aggravates_doshas', [])]

            # Cache the result
            self.cache[chunk_id] = extraction
            self._save_cache()

            return extraction

        except Exception as e:
            print(f"   ⚠️  Error extracting recipe {chunk.get('recipe_name', chunk_id)}: {e}")
            return None

    def process_recipes(self, chunks: List[Dict]):
        """Process all recipe chunks with Claude extraction."""
        print("\n📚 Processing recipes with Claude extraction...")

        recipe_chunks = [c for c in chunks if c.get('is_recipe', False)]
        total = len(recipe_chunks)
        processed = 0
        extracted = 0
        cached = 0

        print(f"   Found {total} recipe chunks")

        # Process in batches
        for i in range(0, total, BATCH_SIZE):
            batch = recipe_chunks[i:i + BATCH_SIZE]

            for chunk in batch:
                chunk_id = str(chunk['id'])

                # Check if already cached
                if chunk_id in self.cache:
                    cached += 1
                    processed += 1
                    continue

                # Extract with Claude
                extraction = self.extract_recipe_with_claude(chunk)
                if extraction:
                    extracted += 1
                processed += 1

                print(f"   Progress: {processed}/{total} (extracted: {extracted}, cached: {cached})", end='\r')

            # Delay between batches (except for last batch)
            if i + BATCH_SIZE < total:
                time.sleep(BATCH_DELAY_SECONDS)

        print(f"\n   ✅ Processed {processed} recipes ({extracted} newly extracted, {cached} from cache)")

    def write_recipes_to_neo4j(self, chunks: List[Dict]):
        """Write all extracted recipes to Neo4j."""
        print("\n💾 Writing recipes to Neo4j...")

        recipe_chunks = [c for c in chunks if c.get('is_recipe', False)]
        written = 0
        skipped = 0

        with self.driver.session() as session:
            for chunk in recipe_chunks:
                chunk_id = str(chunk['id'])
                extraction = self.cache.get(chunk_id)

                if not extraction:
                    skipped += 1
                    continue

                # Get recipe name and validate
                recipe_name = extraction.get('recipe_name', chunk.get('recipe_name', f'Recipe {chunk_id}'))

                # Skip recipes with null or empty names
                if not recipe_name or recipe_name.strip() == '':
                    skipped += 1
                    continue

                # Merge Book node
                source_book = chunk.get('source', 'Unknown')
                session.run("MERGE (:Book {title: $title})", title=source_book)

                # Create Recipe node
                session.run(
                    """
                    MERGE (r:Recipe {name: $name})
                    SET r.source_book = $source_book,
                        r.meal_type = $meal_type,
                        r.prep_time_minutes = $prep_time,
                        r.serves = $serves,
                        r.raw_text = $raw_text,
                        r.notes = $notes,
                        r.chunk_id = $chunk_id
                    """,
                    name=recipe_name,
                    source_book=source_book,
                    meal_type=extraction.get('meal_type'),
                    prep_time=extraction.get('prep_time_minutes'),
                    serves=extraction.get('serves'),
                    raw_text=chunk['text'],
                    notes=extraction.get('notes'),
                    chunk_id=chunk_id
                )

                # Link to Book
                session.run(
                    """
                    MATCH (r:Recipe {name: $recipe})
                    MATCH (b:Book {title: $book})
                    MERGE (r)-[:FROM_SOURCE]->(b)
                    """,
                    recipe=recipe_name,
                    book=source_book
                )

                # Link to Doshas (BALANCES)
                for dosha in extraction.get('balances_doshas', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (d:Dosha {name: $dosha})
                        MERGE (r)-[:BALANCES]->(d)
                        """,
                        recipe=recipe_name,
                        dosha=dosha
                    )

                # Link to Doshas (AGGRAVATES)
                for dosha in extraction.get('aggravates_doshas', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (d:Dosha {name: $dosha})
                        MERGE (r)-[:AGGRAVATES]->(d)
                        """,
                        recipe=recipe_name,
                        dosha=dosha
                    )

                # Link to Imbalances
                for imbalance in extraction.get('helps_with_imbalances', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (i:Imbalance {name: $imbalance})
                        MERGE (r)-[:HELPS_WITH]->(i)
                        """,
                        recipe=recipe_name,
                        imbalance=imbalance
                    )

                # Link to Ingredients
                for ingredient in extraction.get('ingredients', []):
                    session.run("MERGE (:Ingredient {name: $name})", name=ingredient.lower())
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (i:Ingredient {name: $ingredient})
                        MERGE (r)-[:CONTAINS]->(i)
                        """,
                        recipe=recipe_name,
                        ingredient=ingredient.lower()
                    )

                # Link to Tastes
                for taste in extraction.get('tastes', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (t:Taste {name: $taste})
                        MERGE (r)-[:HAS_TASTE]->(t)
                        """,
                        recipe=recipe_name,
                        taste=taste
                    )

                # Link to Qualities
                for quality in extraction.get('qualities', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (q:Quality {name: $quality})
                        MERGE (r)-[:HAS_QUALITY]->(q)
                        """,
                        recipe=recipe_name,
                        quality=quality
                    )

                # Link to Seasons
                for season in extraction.get('suitable_seasons', []):
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (s:Season {name: $season})
                        MERGE (r)-[:SUITS_SEASON]->(s)
                        """,
                        recipe=recipe_name,
                        season=season
                    )

                # Link to MealType
                meal_type = extraction.get('meal_type')
                if meal_type:
                    session.run(
                        """
                        MATCH (r:Recipe {name: $recipe})
                        MATCH (m:MealType {name: $meal_type})
                        MERGE (r)-[:MEAL_TYPE]->(m)
                        """,
                        recipe=recipe_name,
                        meal_type=meal_type
                    )

                written += 1
                print(f"   Progress: {written}/{len(recipe_chunks)}", end='\r')

        print(f"\n   ✅ Wrote {written} recipes to Neo4j ({skipped} skipped)")

    def print_summary(self):
        """Print graph database statistics."""
        print("\n📊 Graph Database Summary")
        print("=" * 50)

        with self.driver.session() as session:
            # Count nodes by type
            node_types = ['Recipe', 'Ingredient', 'Dosha', 'Imbalance', 'Taste', 'Quality', 'Season', 'MealType', 'Book']
            for node_type in node_types:
                result = session.run(f"MATCH (n:{node_type}) RETURN count(n) as count")
                count = result.single()['count']
                print(f"   {node_type:15} {count:>6} nodes")

            print()

            # Count relationships by type
            rel_types = [
                'BALANCES', 'AGGRAVATES', 'CONTAINS', 'HAS_TASTE', 'HAS_QUALITY',
                'SUITS_SEASON', 'MEAL_TYPE', 'FROM_SOURCE', 'HELPS_WITH',
                'COMMON_IMBALANCE', 'NEEDS_TASTE', 'AVOID_TASTE'
            ]
            for rel_type in rel_types:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                count = result.single()['count']
                if count > 0:
                    print(f"   {rel_type:20} {count:>6} relationships")

        print("=" * 50)


def main():
    print("🌿 Building Ayurveda Knowledge Graph")
    print("=" * 50)

    # Verify API key
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not found in .env")
        return

    # Load chunks
    if not Path(CHUNKS_PATH).exists():
        print(f"❌ {CHUNKS_PATH} not found")
        return

    with open(CHUNKS_PATH, 'r') as f:
        chunks = json.load(f)

    print(f"✅ Loaded {len(chunks)} chunks from {CHUNKS_PATH}")

    # Build graph
    builder = GraphBuilder()

    try:
        builder.clear_database()
        builder.seed_base_nodes()
        builder.seed_dosha_taste_relationships()
        builder.process_recipes(chunks)
        builder.write_recipes_to_neo4j(chunks)
        builder.print_summary()

        print("\n✨ Graph build complete!")
        print(f"   Cache saved to: {CACHE_PATH}")
        print(f"   Neo4j browser: http://localhost:7474")

    finally:
        builder.close()


if __name__ == "__main__":
    main()
