#!/usr/bin/env python3
"""
Build Qdrant vector store from theory chunks (non-recipe chunks).
Embeds Ayurvedic wisdom/context for semantic retrieval.
"""

import json
import os
from pathlib import Path
from typing import List, Dict

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv

load_dotenv()

# Configuration
CHUNKS_PATH = "data/chunks.json"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "ayurveda_theory"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384  # Output dimension of all-MiniLM-L6-v2

# Dosha theory reference texts for query expansion
DOSHA_THEORY = {
    "Vata": """Vata dosha governs movement, circulation, and communication in the body.
    Qualities: dry, light, cold, rough, subtle, mobile, clear.
    When balanced: creativity, vitality, flexibility.
    When imbalanced: anxiety, dry skin, constipation, insomnia, scattered thoughts.
    Balancing foods: warm, moist, grounding, nourishing. Sweet, sour, salty tastes.
    Avoid: cold, dry, light foods. Bitter, pungent, astringent tastes.""",

    "Pitta": """Pitta dosha governs transformation, metabolism, and digestion.
    Qualities: hot, sharp, light, liquid, spreading, oily.
    When balanced: intelligence, courage, strong digestion.
    When imbalanced: inflammation, anger, acid reflux, skin rashes, excessive heat.
    Balancing foods: cooling, dry, grounding. Sweet, bitter, astringent tastes.
    Avoid: hot, spicy, oily foods. Sour, salty, pungent tastes.""",

    "Kapha": """Kapha dosha governs structure, lubrication, and stability.
    Qualities: heavy, slow, cold, oily, smooth, soft, stable.
    When balanced: strength, immunity, compassion, patience.
    When imbalanced: congestion, weight gain, lethargy, depression, slow digestion.
    Balancing foods: light, dry, warming, stimulating. Pungent, bitter, astringent tastes.
    Avoid: heavy, oily, cold foods. Sweet, sour, salty tastes."""
}

# Meal type descriptions for context
MEAL_TYPE_DESCRIPTIONS = {
    "Breakfast": "Morning meals that kindle digestive fire, provide sustained energy, and balance morning doshas. Often light to moderate, easy to digest.",
    "Lunch": "Main meal of the day when digestive fire is strongest (11am-2pm). Can include heartier, more complex dishes.",
    "Dinner": "Evening meals that are lighter than lunch, easy to digest, calming. Should be eaten before sunset when possible.",
    "Snack": "Light foods between meals to maintain energy without overwhelming digestion.",
    "Drink": "Beverages, teas, and tonics that support digestion, hydration, and dosha balance.",
    "Dessert": "Sweet treats that satisfy and ground, ideally made with natural sugars and warming spices.",
    "Side": "Accompaniments that complement main dishes and add variety of tastes and qualities.",
    "Condiment": "Chutneys, spice blends, and garnishes that enhance flavor and digestive power."
}


class VectorStoreBuilder:
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        print(f"📡 Loading embedding model: {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ Model loaded (vector size: {VECTOR_SIZE})")

    def recreate_collection(self):
        """Delete and recreate the Qdrant collection."""
        print(f"\n🗑️  Recreating collection '{COLLECTION_NAME}'...")

        # Delete if exists
        try:
            self.client.delete_collection(collection_name=COLLECTION_NAME)
        except Exception:
            pass

        # Create new collection
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        print(f"✅ Collection '{COLLECTION_NAME}' created")

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text using sentence-transformers."""
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in batch."""
        embeddings = self.model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def upsert_theory_chunks(self, chunks: List[Dict]):
        """Upsert theory chunks (non-recipe) to Qdrant."""
        print("\n📚 Processing theory chunks...")

        # Filter to non-recipe chunks only
        theory_chunks = [c for c in chunks if not c.get('is_recipe', False)]
        print(f"   Found {len(theory_chunks)} theory chunks")

        if not theory_chunks:
            print("   ⚠️  No theory chunks found")
            return

        # Prepare points
        points = []
        texts = [chunk['text'] for chunk in theory_chunks]

        print("   Embedding chunks...")
        embeddings = self.embed_batch(texts)

        for i, chunk in enumerate(theory_chunks):
            point = PointStruct(
                id=chunk['id'],
                vector=embeddings[i],
                payload={
                    "chunk_id": chunk['id'],
                    "source": chunk.get('source', 'Unknown'),
                    "doshas": chunk.get('doshas', []),
                    "text": chunk['text'],
                    "type": "theory"
                }
            )
            points.append(point)

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=batch
            )
            print(f"   Progress: {min(i + batch_size, len(points))}/{len(points)}", end='\r')

        print(f"\n   ✅ Upserted {len(points)} theory chunks")

    def upsert_dosha_theory(self):
        """Upsert dosha theory reference texts."""
        print("\n🔮 Upserting dosha theory references...")

        points = []
        point_id = 100000  # Use high IDs to avoid collision with chunks

        for dosha, theory_text in DOSHA_THEORY.items():
            embedding = self.embed_text(theory_text)
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": point_id,
                    "source": "Ayurvedic Knowledge Base",
                    "doshas": [dosha.lower()],
                    "text": theory_text,
                    "type": "dosha_reference"
                }
            )
            points.append(point)
            point_id += 1

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"   ✅ Upserted {len(points)} dosha theory references")

    def upsert_meal_type_descriptions(self):
        """Upsert meal type descriptions for context."""
        print("\n🍽️  Upserting meal type descriptions...")

        points = []
        point_id = 200000  # Use different ID range

        for meal_type, description in MEAL_TYPE_DESCRIPTIONS.items():
            embedding = self.embed_text(description)
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": point_id,
                    "source": "Meal Type Reference",
                    "doshas": [],
                    "text": f"{meal_type}: {description}",
                    "type": "meal_reference"
                }
            )
            points.append(point)
            point_id += 1

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"   ✅ Upserted {len(points)} meal type descriptions")

    def print_summary(self):
        """Print collection statistics."""
        print("\n📊 Vector Store Summary")
        print("=" * 50)

        # Get collection info
        collection_info = self.client.get_collection(collection_name=COLLECTION_NAME)
        print(f"   Collection: {COLLECTION_NAME}")
        print(f"   Total points: {collection_info.points_count}")
        print(f"   Vector size: {VECTOR_SIZE}")
        print(f"   Distance metric: Cosine")

        # Count by type
        types = ['theory', 'dosha_reference', 'meal_reference']
        for type_name in types:
            result = self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter={
                    "must": [
                        {"key": "type", "match": {"value": type_name}}
                    ]
                },
                limit=1,
                with_payload=False,
                with_vectors=False
            )
            # Use count endpoint if available, otherwise estimate
            count_result = self.client.count(
                collection_name=COLLECTION_NAME,
                count_filter={
                    "must": [
                        {"key": "type", "match": {"value": type_name}}
                    ]
                }
            )
            count = count_result.count
            print(f"   {type_name:20} {count:>6} points")

        print("=" * 50)


def main():
    print("🌿 Building Ayurveda Vector Store")
    print("=" * 50)

    # Load chunks
    if not Path(CHUNKS_PATH).exists():
        print(f"❌ {CHUNKS_PATH} not found")
        return

    with open(CHUNKS_PATH, 'r') as f:
        chunks = json.load(f)

    print(f"✅ Loaded {len(chunks)} chunks from {CHUNKS_PATH}")

    # Build vector store
    builder = VectorStoreBuilder()
    builder.recreate_collection()
    builder.upsert_theory_chunks(chunks)
    builder.upsert_dosha_theory()
    builder.upsert_meal_type_descriptions()
    builder.print_summary()

    print("\n✨ Vector store build complete!")
    print(f"   Qdrant dashboard: http://localhost:{QDRANT_PORT}/dashboard")


if __name__ == "__main__":
    main()
