import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import BackButton from '../components/BackButton';
import DoshaPill from '../components/DoshaPill';
import LoadingSpinner from '../components/LoadingSpinner';
import FavoriteButton from '../components/FavoriteButton';
import HeartIcon from '../components/HeartIcon';
import RecipeDetailModal from '../components/RecipeDetailModal';
import './AllRecipesScreen.css';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'favorites', label: 'Favorites', icon: 'heart' },
  { id: 'Vata', label: 'Vata' },
  { id: 'Pitta', label: 'Pitta' },
  { id: 'Kapha', label: 'Kapha' },
];

export default function AllRecipesScreen() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialFilter = searchParams.get('filter') || 'all';

  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState(initialFilter);
  const [detailRecipeKey, setDetailRecipeKey] = useState(null);

  const loadRecipes = useCallback(async () => {
    try {
      setLoading(true);
      const dosha = ['Vata', 'Pitta', 'Kapha'].includes(activeFilter) ? activeFilter : undefined;
      const data = await api.getRecipes({
        search: search.trim() || undefined,
        dosha,
        favoritesOnly: activeFilter === 'favorites',
      });
      setRecipes(data);
    } catch (error) {
      console.error('Failed to load recipes:', error);
    } finally {
      setLoading(false);
    }
  }, [search, activeFilter]);

  useEffect(() => {
    const timer = setTimeout(loadRecipes, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [loadRecipes, search]);

  async function toggleFavorite(e, recipeKey) {
    e.stopPropagation();
    try {
      const result = await api.toggleFavorite(recipeKey);
      setRecipes((prev) =>
        prev.map((r) =>
          r.recipe_key === recipeKey ? { ...r, is_favorited: result.is_favorited } : r
        )
      );
      if (activeFilter === 'favorites' && !result.is_favorited) {
        setRecipes((prev) => prev.filter((r) => r.recipe_key !== recipeKey));
      }
    } catch (error) {
      alert(`Failed to update favorite: ${error.message}`);
    }
  }

  function handleFavoriteToggleFromModal(result) {
    setRecipes((prev) => {
      const updated = prev.map((r) =>
        r.recipe_key === result.recipe_key ? { ...r, is_favorited: result.is_favorited } : r
      );
      if (activeFilter === 'favorites' && !result.is_favorited) {
        return updated.filter((r) => r.recipe_key !== result.recipe_key);
      }
      return updated;
    });
  }

  function openRecipeDetail(recipeKey) {
    setDetailRecipeKey(recipeKey);
  }

  function handleRowKeyDown(e, recipeKey) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openRecipeDetail(recipeKey);
    }
  }

  return (
    <div className="all-recipes-screen">
      <header className="all-recipes-top mobile-only">
        <BackButton onClick={() => navigate('/')} />
        <h1 className="all-recipes-title">All Recipes</h1>
      </header>

      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-header-title">All Recipes</h1>
            <p className="page-header-sub">Browse the whole library — books & your own.</p>
          </div>
          <button type="button" className="btn-header-cta desktop-only" onClick={() => navigate('/recipes/new')}>
            ＋ Write your own recipe
          </button>
        </div>
      </header>

      <div className="recipe-search-wrap">
        <span className="recipe-search-icon">🔍</span>
        <input
          type="search"
          className="recipe-search-input"
          placeholder="Search recipes & ingredients"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="recipe-filters">
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            type="button"
            className={`recipe-filter ${activeFilter === filter.id ? 'active' : ''} ${filter.id !== 'all' && filter.id !== 'favorites' ? `recipe-filter--${filter.id.toLowerCase()}` : ''}`}
            onClick={() => setActiveFilter(filter.id)}
          >
            {filter.icon === 'heart' ? (
              <>
                <HeartIcon filled={activeFilter === filter.id} size={13} />
                {' '}
                {filter.label}
              </>
            ) : (
              filter.label
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <LoadingSpinner message="Loading recipes..." />
      ) : recipes.length === 0 ? (
        <div className="all-recipes-empty">
          <p>No recipes found.</p>
          {activeFilter === 'favorites' && (
            <p className="all-recipes-empty-hint">Tap the heart on any recipe to save it here.</p>
          )}
        </div>
      ) : (
        <div className="all-recipes-list">
          {recipes.map((recipe) => (
            <div
              key={recipe.recipe_key}
              className={`recipe-row recipe-row--clickable ${recipe.is_custom ? 'recipe-row--custom' : ''}`}
              role="button"
              tabIndex={0}
              onClick={() => openRecipeDetail(recipe.recipe_key)}
              onKeyDown={(e) => handleRowKeyDown(e, recipe.recipe_key)}
            >
              <div className="recipe-row-body">
                <div className="recipe-row-title-row">
                  <div className="recipe-row-name">{recipe.name}</div>
                  {recipe.is_custom && <span className="recipe-my-badge">My recipe</span>}
                </div>
                <div className="recipe-row-source">
                  {recipe.is_custom ? '✍️ Written by you' : `📖 ${recipe.source || 'Unknown source'}`}
                </div>
                {recipe.doshas.length > 0 && (
                  <div className="recipe-row-doshas">
                    {recipe.doshas.map((d) => (
                      <DoshaPill key={d} dosha={d} variant="outline" size="md" />
                    ))}
                  </div>
                )}
              </div>
              <FavoriteButton
                active={recipe.is_favorited}
                onClick={(e) => toggleFavorite(e, recipe.recipe_key)}
              />
            </div>
          ))}
        </div>
      )}

      <div className="all-recipes-footer mobile-only">
        <button type="button" className="btn-cta" onClick={() => navigate('/recipes/new')}>
          ＋ Write your own recipe
        </button>
      </div>

      <RecipeDetailModal
        isOpen={detailRecipeKey !== null}
        onClose={() => setDetailRecipeKey(null)}
        recipeKey={detailRecipeKey}
        onFavoriteToggle={handleFavoriteToggleFromModal}
      />
    </div>
  );
}
