"""
FastAPI backend for Ayurveda recipe recommendation system.
Exposes REST API for profile/people management and dual-store RAG suggestions.
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db
from models import (
    Profile, Person, DoshaAssignment, DoshaImbalance, SuggestionHistory,
    CustomRecipe, RecipeFavorite,
)
from rag import DualStoreRAG, normalize_person_doshas, extract_recipe_names_from_suggestion

RECENT_RECIPE_DAYS = 7


# Pydantic models for API
class DoshaAssignmentCreate(BaseModel):
    dosha: str
    is_primary: bool
    tendency: Optional[str] = None  # 'excess' or 'deficiency'


class PersonCreate(BaseModel):
    name: str
    serving_count: int = 1
    doshas: List[DoshaAssignmentCreate]
    imbalances: List[str] = []


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    serving_count: Optional[int] = None
    doshas: Optional[List[DoshaAssignmentCreate]] = None
    imbalances: Optional[List[str]] = None


class ProfileCreate(BaseModel):
    name: str


class DoshaAssignmentResponse(BaseModel):
    dosha: str
    is_primary: bool
    tendency: Optional[str] = None

    class Config:
        from_attributes = True


class PersonResponse(BaseModel):
    id: int
    name: str
    serving_count: int
    doshas: List[DoshaAssignmentResponse]
    imbalances: List[str]

    class Config:
        from_attributes = True


class ProfileResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_used_at: datetime
    people_count: int

    class Config:
        from_attributes = True


class CombinedSuggestion(BaseModel):
    meal_harmony_note: str
    recipes: List[dict]


class IndividualSuggestion(BaseModel):
    person_name: str
    meal_note: Optional[str] = None
    recipes: List[dict]


class SuggestionResponse(BaseModel):
    recipes: List[dict]
    meal_harmony_note: str
    combined: CombinedSuggestion
    individual: List[IndividualSuggestion] = []
    graph_recipe_count: int
    vector_chunk_count: int


class HistoryItemResponse(BaseModel):
    id: int
    suggested_at: datetime
    people_snapshot: List[dict]
    response_json: dict
    graph_recipe_count: int
    vector_chunk_count: int
    cooked_recipes: List[str] = []

    class Config:
        from_attributes = True


class CookRecipeRequest(BaseModel):
    recipe_name: str


class CustomRecipeCreate(BaseModel):
    name: str
    source: Optional[str] = None
    ingredients: List[str] = []
    method_notes: Optional[str] = None
    doshas: List[str] = []
    imbalances: List[str] = []


class CustomRecipeUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    ingredients: Optional[List[str]] = None
    method_notes: Optional[str] = None
    doshas: Optional[List[str]] = None
    imbalances: Optional[List[str]] = None


class CustomRecipeResponse(BaseModel):
    id: int
    name: str
    source: Optional[str]
    ingredients: List[str]
    method_notes: Optional[str]
    doshas: List[str]
    imbalances: List[str] = []
    created_at: datetime
    is_custom: bool = True
    is_favorited: bool = False
    recipe_key: str

    class Config:
        from_attributes = True


class RecipeListItem(BaseModel):
    id: Optional[int] = None
    recipe_key: str
    name: str
    source: Optional[str]
    doshas: List[str]
    ingredients: List[str]
    is_custom: bool
    is_favorited: bool


class FavoriteToggleRequest(BaseModel):
    recipe_key: str


class FavoriteToggleResponse(BaseModel):
    recipe_key: str
    is_favorited: bool


class RecipeDetailResponse(BaseModel):
    recipe_key: str
    name: str
    source: Optional[str] = None
    doshas: List[str] = []
    imbalances: List[str] = []
    ingredients: List[str] = []
    method_notes: Optional[str] = None
    is_custom: bool = False
    is_favorited: bool = False


def get_recent_suggestion_context(profile_id: int, db: Session) -> Tuple[List[str], List[str]]:
    """Recipe names and wisdom chunk IDs suggested in the last RECENT_RECIPE_DAYS days (for variety)."""
    cutoff = datetime.utcnow() - timedelta(days=RECENT_RECIPE_DAYS)
    entries = (
        db.query(SuggestionHistory)
        .filter(
            SuggestionHistory.profile_id == profile_id,
            SuggestionHistory.suggested_at >= cutoff,
        )
        .order_by(SuggestionHistory.suggested_at.desc())
        .all()
    )

    recipe_names: List[str] = []
    chunk_ids: List[str] = []
    seen_recipes = set()
    seen_chunks = set()

    for entry in entries:
        # Extract recipe names
        try:
            data = json.loads(entry.response_json)
        except json.JSONDecodeError:
            continue
        for name in extract_recipe_names_from_suggestion(data):
            if name not in seen_recipes:
                seen_recipes.add(name)
                recipe_names.append(name)

        # Extract chunk IDs
        try:
            chunk_id_list = json.loads(entry.vector_chunk_ids) if entry.vector_chunk_ids else []
            for chunk_id in chunk_id_list:
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    chunk_ids.append(chunk_id)
        except (json.JSONDecodeError, AttributeError):
            continue

    return recipe_names, chunk_ids


def serialize_history_item(entry: SuggestionHistory) -> HistoryItemResponse:
    cooked_raw = getattr(entry, 'cooked_recipes', None) or '[]'
    cooked = json.loads(cooked_raw) if cooked_raw else []
    return HistoryItemResponse(
        id=entry.id,
        suggested_at=entry.suggested_at,
        people_snapshot=json.loads(entry.people_snapshot),
        response_json=json.loads(entry.response_json),
        graph_recipe_count=entry.graph_recipe_count,
        vector_chunk_count=entry.vector_chunk_count,
        cooked_recipes=cooked,
    )


def custom_recipe_key(recipe_id: int) -> str:
    return f"custom:{recipe_id}"


def list_graph_recipes(search: Optional[str] = None) -> List[dict]:
    """Fetch recipes from Neo4j knowledge graph."""
    query = """
    MATCH (r:Recipe)
    OPTIONAL MATCH (r)-[:BALANCES]->(d:Dosha)
    OPTIONAL MATCH (r)-[:CONTAINS]->(i:Ingredient)
    WITH r, collect(DISTINCT d.name) AS doshas, collect(DISTINCT i.name) AS ingredients
    RETURN r.name AS name,
           r.source_book AS source,
           doshas,
           ingredients
    ORDER BY toLower(r.name)
    """
    with rag_system.neo4j_driver.session() as session:
        results = session.run(query)
        recipes = []
        for record in results:
            name = record['name']
            if not name:
                continue
            if search:
                needle = search.lower()
                haystack = ' '.join([
                    name,
                    record['source'] or '',
                    ' '.join(record['ingredients'] or []),
                ]).lower()
                if needle not in haystack:
                    continue
            recipes.append({
                'name': name,
                'source': record['source'],
                'doshas': [d for d in (record['doshas'] or []) if d],
                'ingredients': record['ingredients'] or [],
            })
        return recipes


def get_graph_recipe_detail(name: str) -> Optional[dict]:
    """Fetch a single graph recipe with full text from Neo4j."""
    query = """
    MATCH (r:Recipe {name: $name})
    OPTIONAL MATCH (r)-[:BALANCES]->(d:Dosha)
    OPTIONAL MATCH (r)-[:CONTAINS]->(i:Ingredient)
    OPTIONAL MATCH (r)-[:HELPS_WITH]->(imb:Imbalance)
    WITH r,
         collect(DISTINCT d.name) AS doshas,
         collect(DISTINCT i.name) AS ingredients,
         collect(DISTINCT imb.name) AS imbalances
    RETURN r.name AS name,
           r.source_book AS source,
           r.raw_text AS raw_text,
           r.notes AS notes,
           doshas,
           ingredients,
           imbalances
    LIMIT 1
    """
    with rag_system.neo4j_driver.session() as session:
        record = session.run(query, name=name).single()
        if not record or not record['name']:
            return None

        raw_text = (record['raw_text'] or '').strip()
        notes = (record['notes'] or '').strip()
        method_parts = []
        if raw_text:
            method_parts.append(raw_text)
        if notes and notes != raw_text:
            method_parts.append(notes)

        return {
            'name': record['name'],
            'source': record['source'],
            'doshas': [d for d in (record['doshas'] or []) if d],
            'imbalances': [imb for imb in (record['imbalances'] or []) if imb],
            'ingredients': record['ingredients'] or [],
            'method_notes': '\n\n'.join(method_parts) if method_parts else None,
        }


def serialize_custom_recipe(recipe: CustomRecipe, favorite_keys: set) -> dict:
    key = custom_recipe_key(recipe.id)
    return {
        'id': recipe.id,
        'recipe_key': key,
        'name': recipe.name,
        'source': recipe.source,
        'ingredients': json.loads(recipe.ingredients or '[]'),
        'method_notes': recipe.method_notes,
        'doshas': json.loads(recipe.doshas or '[]'),
        'imbalances': json.loads(getattr(recipe, 'imbalances', None) or '[]'),
        'created_at': recipe.created_at,
        'is_custom': True,
        'is_favorited': key in favorite_keys,
    }


# Global RAG instance
rag_system: Optional[DualStoreRAG] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global rag_system

    print("🌿 Starting Ayurveda Recipe API...")

    # Initialize database
    init_db()

    # Initialize RAG system
    print("📡 Initializing dual-store RAG system...")
    rag_system = DualStoreRAG()
    print("✅ RAG system ready")

    yield

    # Cleanup
    if rag_system:
        rag_system.close()
    print("👋 Shutting down")


# Create FastAPI app
app = FastAPI(
    title="Ayurveda Recipe API",
    description="Dual-store RAG system for personalized Ayurvedic recipe recommendations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware — allow any localhost port in dev (Vite may use 5173, 5174, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://app.ossagent.net",
        "https://ossagentapp-ujzb5.ondigitalocean.app",
    ],
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
def health_check():
    """Check system health and database stats."""
    try:
        # Check Neo4j
        with rag_system.neo4j_driver.session() as session:
            result = session.run("MATCH (n:Recipe) RETURN count(n) as count")
            neo4j_recipe_count = result.single()['count']

        # Check Qdrant
        collection_info = rag_system.qdrant_client.get_collection(collection_name="ayurveda_theory")
        qdrant_points = collection_info.points_count

        # Check model
        model_loaded = rag_system.embedding_model is not None

        return {
            "status": "healthy",
            "neo4j_recipe_count": neo4j_recipe_count,
            "qdrant_points": qdrant_points,
            "model_loaded": model_loaded,
            "db_ok": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Profile endpoints
@app.get("/profiles", response_model=List[ProfileResponse])
def get_profiles(db: Session = Depends(get_db)):
    """Get all profiles."""
    profiles = db.query(Profile).all()
    return [
        ProfileResponse(
            id=p.id,
            name=p.name,
            created_at=p.created_at,
            last_used_at=p.last_used_at,
            people_count=len(p.people)
        )
        for p in profiles
    ]


@app.post("/profiles", response_model=ProfileResponse)
def create_profile(profile: ProfileCreate, db: Session = Depends(get_db)):
    """Create a new profile."""
    # Check if name already exists
    existing = db.query(Profile).filter(Profile.name == profile.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile name already exists")

    new_profile = Profile(name=profile.name)
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return ProfileResponse(
        id=new_profile.id,
        name=new_profile.name,
        created_at=new_profile.created_at,
        last_used_at=new_profile.last_used_at,
        people_count=0
    )


@app.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """Delete a profile and all associated data."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return {"message": "Profile deleted successfully"}


# People endpoints
@app.get("/profiles/{profile_id}/people", response_model=List[PersonResponse])
def get_people(profile_id: int, db: Session = Depends(get_db)):
    """Get all people in a profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    people_responses = []
    for person in profile.people:
        dosha_assignments = [
            DoshaAssignmentResponse(dosha=da.dosha, is_primary=da.is_primary, tendency=da.tendency)
            for da in person.dosha_assignments
        ]
        imbalances = [imb.imbalance for imb in person.imbalances]

        people_responses.append(PersonResponse(
            id=person.id,
            name=person.name,
            serving_count=person.serving_count,
            doshas=dosha_assignments,
            imbalances=imbalances
        ))

    return people_responses


@app.post("/profiles/{profile_id}/people", response_model=PersonResponse)
def create_person(profile_id: int, person_data: PersonCreate, db: Session = Depends(get_db)):
    """Add a person to a profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Create person
    new_person = Person(
        profile_id=profile_id,
        name=person_data.name,
        serving_count=person_data.serving_count
    )
    db.add(new_person)
    db.flush()

    # Add dosha assignments
    for dosha_data in person_data.doshas:
        assignment = DoshaAssignment(
            person_id=new_person.id,
            dosha=dosha_data.dosha,
            is_primary=dosha_data.is_primary,
            tendency=dosha_data.tendency,
        )
        db.add(assignment)

    # Add imbalances
    for imbalance_name in person_data.imbalances:
        imbalance = DoshaImbalance(
            person_id=new_person.id,
            imbalance=imbalance_name
        )
        db.add(imbalance)

    db.commit()
    db.refresh(new_person)

    return PersonResponse(
        id=new_person.id,
        name=new_person.name,
        serving_count=new_person.serving_count,
        doshas=[DoshaAssignmentResponse(dosha=da.dosha, is_primary=da.is_primary, tendency=da.tendency) for da in new_person.dosha_assignments],
        imbalances=[imb.imbalance for imb in new_person.imbalances]
    )


@app.put("/people/{person_id}", response_model=PersonResponse)
def update_person(person_id: int, person_data: PersonUpdate, db: Session = Depends(get_db)):
    """Update a person's data."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Update basic fields
    if person_data.name is not None:
        person.name = person_data.name
    if person_data.serving_count is not None:
        person.serving_count = person_data.serving_count

    # Update doshas if provided
    if person_data.doshas is not None:
        # Delete existing assignments
        db.query(DoshaAssignment).filter(DoshaAssignment.person_id == person_id).delete()

        # Add new assignments
        for dosha_data in person_data.doshas:
            assignment = DoshaAssignment(
                person_id=person_id,
                dosha=dosha_data.dosha,
                is_primary=dosha_data.is_primary,
                tendency=dosha_data.tendency,
            )
            db.add(assignment)

    # Update imbalances if provided
    if person_data.imbalances is not None:
        # Delete existing imbalances
        db.query(DoshaImbalance).filter(DoshaImbalance.person_id == person_id).delete()

        # Add new imbalances
        for imbalance_name in person_data.imbalances:
            imbalance = DoshaImbalance(
                person_id=person_id,
                imbalance=imbalance_name
            )
            db.add(imbalance)

    db.commit()
    db.refresh(person)

    return PersonResponse(
        id=person.id,
        name=person.name,
        serving_count=person.serving_count,
        doshas=[DoshaAssignmentResponse(dosha=da.dosha, is_primary=da.is_primary, tendency=da.tendency) for da in person.dosha_assignments],
        imbalances=[imb.imbalance for imb in person.imbalances]
    )


@app.delete("/people/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete a person."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    db.delete(person)
    db.commit()
    return {"message": "Person deleted successfully"}


# Suggestion endpoint (main RAG)
@app.post("/profiles/{profile_id}/suggest", response_model=SuggestionResponse)
def suggest_recipes(profile_id: int, db: Session = Depends(get_db)):
    """Generate recipe suggestions using dual-store RAG."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not profile.people:
        raise HTTPException(status_code=400, detail="Profile must have at least one person")

    # Build people data for RAG
    people_data = []
    for person in profile.people:
        doshas = normalize_person_doshas([
            {"dosha": da.dosha, "is_primary": da.is_primary, "tendency": da.tendency}
            for da in person.dosha_assignments
        ])
        imbalances = [imb.imbalance for imb in person.imbalances]

        people_data.append({
            "name": person.name,
            "serving_count": person.serving_count,
            "doshas": doshas,
            "imbalances": imbalances
        })

    # Deprioritize recipes suggested in the last 7 days for daily variety
    recent_recipes, recent_chunks = get_recent_suggestion_context(profile_id, db)

    # Call RAG system
    try:
        result = rag_system.suggest_recipes(
            people_data,
            recent_recipe_names=recent_recipes,
            recent_wisdom_chunk_ids=recent_chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG system error: {str(e)}")

    # Save to history
    history_entry = SuggestionHistory(
        profile_id=profile_id,
        response_json=json.dumps(result),
        people_snapshot=json.dumps(people_data),
        graph_recipe_count=result['graph_recipe_count'],
        vector_chunk_count=result['vector_chunk_count'],
        vector_chunk_ids=json.dumps(result.get('vector_chunk_ids', [])),
        cooked_recipes='[]',
    )
    db.add(history_entry)

    # Update profile last_used_at
    profile.last_used_at = datetime.utcnow()
    db.commit()

    return SuggestionResponse(
        recipes=result['recipes'],
        meal_harmony_note=result['meal_harmony_note'],
        combined=result['combined'],
        individual=result.get('individual', []),
        graph_recipe_count=result['graph_recipe_count'],
        vector_chunk_count=result['vector_chunk_count']
    )


# History endpoint
@app.get("/profiles/{profile_id}/history", response_model=List[HistoryItemResponse])
def get_suggestion_history(profile_id: int, db: Session = Depends(get_db)):
    """Get suggestion history for a profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    history = (
        db.query(SuggestionHistory)
        .filter(SuggestionHistory.profile_id == profile_id)
        .order_by(SuggestionHistory.suggested_at.desc())
        .all()
    )

    return [serialize_history_item(h) for h in history]


@app.post("/history/{history_id}/cooked/toggle", response_model=HistoryItemResponse)
def toggle_recipe_cooked(history_id: int, payload: CookRecipeRequest, db: Session = Depends(get_db)):
    """Mark or unmark a suggested recipe as cooked."""
    entry = db.query(SuggestionHistory).filter(SuggestionHistory.id == history_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")

    recipe_name = payload.recipe_name.strip()
    if not recipe_name:
        raise HTTPException(status_code=400, detail="Recipe name is required")

    cooked = json.loads(entry.cooked_recipes) if entry.cooked_recipes else []
    if recipe_name in cooked:
        cooked = [name for name in cooked if name != recipe_name]
    else:
        cooked = [*cooked, recipe_name]

    entry.cooked_recipes = json.dumps(cooked)
    db.commit()
    db.refresh(entry)
    return serialize_history_item(entry)


# Recipe browse & custom recipe endpoints
@app.get("/recipes", response_model=List[RecipeListItem])
def list_recipes(
    search: Optional[str] = None,
    dosha: Optional[str] = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
):
    """List graph recipes and user-written custom recipes."""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not ready")

    favorite_keys = {f.recipe_key for f in db.query(RecipeFavorite).all()}
    items: List[RecipeListItem] = []

    for graph_recipe in list_graph_recipes(search=search):
        key = graph_recipe['name']
        is_favorited = key in favorite_keys
        if favorites_only and not is_favorited:
            continue
        recipe_doshas = graph_recipe['doshas']
        if dosha and dosha not in recipe_doshas:
            continue
        items.append(RecipeListItem(
            id=None,
            recipe_key=key,
            name=graph_recipe['name'],
            source=graph_recipe['source'],
            doshas=recipe_doshas,
            ingredients=graph_recipe['ingredients'],
            is_custom=False,
            is_favorited=is_favorited,
        ))

    for custom in db.query(CustomRecipe).order_by(CustomRecipe.created_at.desc()).all():
        data = serialize_custom_recipe(custom, favorite_keys)
        if search:
            needle = search.lower()
            haystack = ' '.join([
                data['name'],
                data['source'] or '',
                ' '.join(data['ingredients']),
                data['method_notes'] or '',
            ]).lower()
            if needle not in haystack:
                continue
        if dosha and dosha not in data['doshas']:
            continue
        if favorites_only and not data['is_favorited']:
            continue
        items.append(RecipeListItem(
            id=data['id'],
            recipe_key=data['recipe_key'],
            name=data['name'],
            source=data['source'] or 'Written by you',
            doshas=data['doshas'],
            ingredients=data['ingredients'],
            is_custom=True,
            is_favorited=data['is_favorited'],
        ))

    # Custom recipes first when names tie; otherwise alphabetical
    items.sort(key=lambda r: (not r.is_custom, r.name.lower()))
    return items


@app.get("/recipes/detail", response_model=RecipeDetailResponse)
def get_recipe_detail(key: str, db: Session = Depends(get_db)):
    """Return full recipe details for a graph or custom recipe key."""
    if not key.strip():
        raise HTTPException(status_code=400, detail="Recipe key is required")

    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not ready")

    favorite_keys = {f.recipe_key for f in db.query(RecipeFavorite).all()}

    if key.startswith("custom:"):
        try:
            recipe_id = int(key.split(":", 1)[1])
        except (IndexError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid custom recipe key")

        recipe = db.query(CustomRecipe).filter(CustomRecipe.id == recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        data = serialize_custom_recipe(recipe, favorite_keys)
        return RecipeDetailResponse(
            recipe_key=data['recipe_key'],
            name=data['name'],
            source=data['source'] or 'Written by you',
            doshas=data['doshas'],
            imbalances=data['imbalances'],
            ingredients=data['ingredients'],
            method_notes=data['method_notes'],
            is_custom=True,
            is_favorited=data['is_favorited'],
        )

    graph_recipe = get_graph_recipe_detail(key)
    if not graph_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return RecipeDetailResponse(
        recipe_key=key,
        name=graph_recipe['name'],
        source=graph_recipe['source'],
        doshas=graph_recipe['doshas'],
        imbalances=graph_recipe.get('imbalances', []),
        ingredients=graph_recipe['ingredients'],
        method_notes=graph_recipe['method_notes'],
        is_custom=False,
        is_favorited=key in favorite_keys,
    )


@app.get("/recipes/favorites", response_model=List[str])
def get_favorite_keys(db: Session = Depends(get_db)):
    """Return all favorited recipe keys."""
    return [f.recipe_key for f in db.query(RecipeFavorite).order_by(RecipeFavorite.created_at.desc()).all()]


@app.post("/recipes/favorites/toggle", response_model=FavoriteToggleResponse)
def toggle_favorite(payload: FavoriteToggleRequest, db: Session = Depends(get_db)):
    """Toggle favorite status for a graph or custom recipe."""
    existing = db.query(RecipeFavorite).filter(RecipeFavorite.recipe_key == payload.recipe_key).first()
    if existing:
        db.delete(existing)
        db.commit()
        return FavoriteToggleResponse(recipe_key=payload.recipe_key, is_favorited=False)

    db.add(RecipeFavorite(recipe_key=payload.recipe_key))
    db.commit()
    return FavoriteToggleResponse(recipe_key=payload.recipe_key, is_favorited=True)


@app.post("/recipes/custom", response_model=CustomRecipeResponse)
def create_custom_recipe(recipe: CustomRecipeCreate, db: Session = Depends(get_db)):
    """Save a user-written recipe."""
    if not recipe.name.strip():
        raise HTTPException(status_code=400, detail="Recipe name is required")

    new_recipe = CustomRecipe(
        name=recipe.name.strip(),
        source=recipe.source.strip() if recipe.source else None,
        ingredients=json.dumps(recipe.ingredients),
        method_notes=recipe.method_notes,
        doshas=json.dumps(recipe.doshas),
        imbalances=json.dumps(recipe.imbalances),
    )
    db.add(new_recipe)
    db.commit()
    db.refresh(new_recipe)

    favorite_keys = {f.recipe_key for f in db.query(RecipeFavorite).all()}
    data = serialize_custom_recipe(new_recipe, favorite_keys)
    return CustomRecipeResponse(**data)


@app.get("/recipes/custom/{recipe_id}", response_model=CustomRecipeResponse)
def get_custom_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Get a single custom recipe for editing."""
    recipe = db.query(CustomRecipe).filter(CustomRecipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    favorite_keys = {f.recipe_key for f in db.query(RecipeFavorite).all()}
    return CustomRecipeResponse(**serialize_custom_recipe(recipe, favorite_keys))


@app.put("/recipes/custom/{recipe_id}", response_model=CustomRecipeResponse)
def update_custom_recipe(recipe_id: int, recipe: CustomRecipeUpdate, db: Session = Depends(get_db)):
    """Update a user-written recipe."""
    existing = db.query(CustomRecipe).filter(CustomRecipe.id == recipe_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.name is not None:
        if not recipe.name.strip():
            raise HTTPException(status_code=400, detail="Recipe name is required")
        existing.name = recipe.name.strip()
    if recipe.source is not None:
        existing.source = recipe.source.strip() or None
    if recipe.ingredients is not None:
        existing.ingredients = json.dumps(recipe.ingredients)
    if recipe.method_notes is not None:
        existing.method_notes = recipe.method_notes
    if recipe.doshas is not None:
        existing.doshas = json.dumps(recipe.doshas)
    if recipe.imbalances is not None:
        existing.imbalances = json.dumps(recipe.imbalances)

    db.commit()
    db.refresh(existing)

    favorite_keys = {f.recipe_key for f in db.query(RecipeFavorite).all()}
    return CustomRecipeResponse(**serialize_custom_recipe(existing, favorite_keys))


@app.delete("/recipes/custom/{recipe_id}")
def delete_custom_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Delete a user-written recipe."""
    recipe = db.query(CustomRecipe).filter(CustomRecipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    db.query(RecipeFavorite).filter(RecipeFavorite.recipe_key == custom_recipe_key(recipe_id)).delete()
    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
