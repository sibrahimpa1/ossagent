import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { FitBadge } from '../components/DoshaPill';
import DoshaText from '../components/DoshaText';
import LoadingSpinner, { GENERATION_MESSAGES } from '../components/LoadingSpinner';
import FavoriteButton from '../components/FavoriteButton';
import BackButton from '../components/BackButton';
import { getTodaySuggestion, sessionToSuggestionResult } from '../utils/history';
import './SuggestionScreen.css';

function fitCardClass(fit) {
  const key = (fit || 'Works').toLowerCase();
  return `result-recipe-card result-recipe-card--${key}`;
}

function StatsPills({ graphCount, vectorCount }) {
  return (
    <div className="suggestion-stats">
      <span className="suggestion-stat-pill suggestion-stat-pill--graph">
        🕸️ {graphCount} graph recipes
      </span>
      <span className="suggestion-stat-pill suggestion-stat-pill--wisdom">
        📚 {vectorCount} from cookbooks
      </span>
    </div>
  );
}

function parseIngredients(recipe) {
  if (recipe.ingredients?.length) return recipe.ingredients;
  if (typeof recipe.substitutions === 'string') return [];
  return [];
}

function RecipeCard({
  recipe,
  cardKey,
  isExpanded,
  onToggleExpanded,
  isFavorited,
  onToggleFavorite,
}) {
  const ingredients = parseIngredients(recipe);
  const bestForPerson = recipe.per_person?.[0];

  return (
    <div className={fitCardClass(recipe.overall_fit)}>
      <div className="result-recipe-header">
        <div className="result-recipe-name">{recipe.name}</div>
        <div className="result-recipe-badges">
          <FavoriteButton
            active={isFavorited}
            title={isFavorited ? 'Saved to favorites' : 'Add to favorites'}
            onClick={() => onToggleFavorite(recipe.name)}
          />
          <FitBadge fit={recipe.overall_fit} />
        </div>
      </div>

      {recipe.source && (
        <div className="result-recipe-source">
          <span>📖</span> from <strong>{recipe.source}</strong>
        </div>
      )}

      {recipe.why_it_works && (
        <p className="result-recipe-desc">
          <DoshaText text={recipe.why_it_works} />
        </p>
      )}

      {ingredients.length > 0 && (
        <div className="ingredients-section">
          <div className="ingredients-label">Ingredients</div>
          <div className="ingredients-tags">
            {ingredients.map((ing, i) => (
              <span key={i} className="ingredient-tag">{ing}</span>
            ))}
          </div>
        </div>
      )}

      {bestForPerson && (
        <div className="best-for-card">
          <div className="best-for-avatar">{bestForPerson.name?.[0] || '?'}</div>
          <div>
            <div className="best-for-label">Best for</div>
            <div className="best-for-name">{bestForPerson.name}</div>
          </div>
        </div>
      )}

      {recipe.substitutions && (
        <div className="substitution-tip">
          <span>💡</span>
          <span><DoshaText text={recipe.substitutions} /></span>
        </div>
      )}

      {recipe.per_person?.length > 0 && (
        <div className="breakdown-section">
          <button
            type="button"
            className="breakdown-toggle"
            onClick={() => onToggleExpanded(cardKey)}
          >
            <span>Per person breakdown</span>
            <span>{isExpanded ? '▾' : '▸'}</span>
          </button>
          {isExpanded && (
            <div className="breakdown-rows">
              {recipe.per_person.map((person, i) => (
                <div key={i} className="breakdown-row">
                  <span className="breakdown-name">{person.name}</span>
                  <FitBadge fit={person.fit} size="sm" />
                  <span className="breakdown-note">
                    <DoshaText text={person.note || person.reason || ''} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RecipeSection({
  title,
  subtitle,
  note,
  recipes,
  sectionKey,
  sectionId,
  sectionRef,
  expandedRecipes,
  onToggleExpanded,
  favoriteKeys,
  onToggleFavorite,
}) {
  if (!recipes?.length) return null;

  return (
    <section
      ref={sectionRef}
      id={sectionId}
      className="suggestion-section"
    >
      <div className="suggestion-section-header">
        <h2 className="suggestion-section-title">{title}</h2>
        {subtitle && <p className="suggestion-section-subtitle">{subtitle}</p>}
      </div>

      {note && (
        <div className="harmony-block suggestion-section-note">
          <p><DoshaText text={note} /></p>
        </div>
      )}

      <div className="recipe-list">
        {recipes.map((recipe, index) => {
          const cardKey = `${sectionKey}-${index}`;
          return (
            <RecipeCard
              key={cardKey}
              recipe={recipe}
              cardKey={cardKey}
              isExpanded={expandedRecipes.has(cardKey)}
              onToggleExpanded={onToggleExpanded}
              isFavorited={favoriteKeys.has(recipe.name)}
              onToggleFavorite={onToggleFavorite}
            />
          );
        })}
      </div>
    </section>
  );
}

function personSectionId(name) {
  return `suggestion-person-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
}

function SuggestionNavTabs({ activeTab, people, onSelect, className = '' }) {
  return (
    <nav className={`suggestion-nav-tabs ${className}`.trim()} aria-label="Recipe sections">
      <div className="suggestion-nav-tabs-scroll">
        <button
          type="button"
          className={`suggestion-nav-tab ${activeTab === 'together' ? 'active' : ''}`}
          onClick={() => onSelect('together')}
        >
          Cook together
        </button>
        {people.map((personSection) => {
          const tabId = personSection.person_name;
          return (
            <button
              key={tabId}
              type="button"
              className={`suggestion-nav-tab ${activeTab === tabId ? 'active' : ''}`}
              onClick={() => onSelect(tabId)}
            >
              {personSection.person_name}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export default function SuggestionScreen() {
  const { profileId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [expandedRecipes, setExpandedRecipes] = useState(new Set(['combined-0']));
  const [favoriteKeys, setFavoriteKeys] = useState(new Set());
  const [activeTab, setActiveTab] = useState('together');
  const combinedRef = useRef(null);

  useEffect(() => {
    loadSuggestions();
    api.getFavoriteKeys().then((keys) => setFavoriteKeys(new Set(keys))).catch(() => {});
  }, [profileId]);

  useEffect(() => {
    const individual = result?.individual || [];
    if (!result || individual.length === 0) return undefined;

    let observer;

    const frame = requestAnimationFrame(() => {
      const combinedEl = combinedRef.current;
      const personEls = individual
        .map((section) => document.getElementById(personSectionId(section.person_name)))
        .filter(Boolean);
      const observed = [combinedEl, ...personEls].filter(Boolean);
      if (!observed.length) return;

      observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
          if (!visible.length) return;

          const target = visible[0].target;
          if (target === combinedEl) {
            setActiveTab('together');
            return;
          }

          const matchedPerson = individual.find(
            (section) => target.id === personSectionId(section.person_name)
          );
          if (matchedPerson) setActiveTab(matchedPerson.person_name);
        },
        { rootMargin: '-12% 0px -55% 0px', threshold: [0, 0.15, 0.35, 0.6] }
      );

      observed.forEach((el) => observer.observe(el));
    });

    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [result]);

  function scrollToSection(tab) {
    setActiveTab(tab);
    const target = tab === 'together'
      ? combinedRef.current
      : document.getElementById(personSectionId(tab));
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function loadSuggestions({ regenerate = false } = {}) {
    try {
      if (regenerate) setRegenerating(true);
      else {
        setLoading(true);
        setIsGenerating(false);
      }
      setError(null);

      if (!regenerate) {
        const history = await api.getHistory(profileId);
        const todaySession = getTodaySuggestion(history);
        if (todaySession) {
          setResult(sessionToSuggestionResult(todaySession));
          return;
        }
      }

      setIsGenerating(true);
      const data = await api.getSuggestions(profileId);
      setResult({ ...data, from_cache: false });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setIsGenerating(false);
      setRegenerating(false);
    }
  }

  function toggleRecipeExpanded(cardKey) {
    setExpandedRecipes((prev) => {
      const next = new Set(prev);
      if (next.has(cardKey)) next.delete(cardKey);
      else next.add(cardKey);
      return next;
    });
  }

  async function toggleFavorite(recipeName) {
    try {
      const favResult = await api.toggleFavorite(recipeName);
      setFavoriteKeys((prev) => {
        const next = new Set(prev);
        if (favResult.is_favorited) next.add(recipeName);
        else next.delete(recipeName);
        return next;
      });
    } catch (err) {
      alert(`Failed to update favorite: ${err.message}`);
    }
  }

  if (loading) {
    return (
      <LoadingSpinner
        message={isGenerating ? undefined : "Loading today's recipes..."}
        messages={GENERATION_MESSAGES}
      />
    );
  }

  if (error) {
    return (
      <div className="suggestion-screen">
        <div className="error-state">
          <h2>Something went wrong</h2>
          <p>{error}</p>
          <button type="button" className="btn-outline" onClick={() => navigate(`/profile/${profileId}`)}>
            ↩ Back to Profile
          </button>
          <button type="button" className="btn-cta error-retry" onClick={() => loadSuggestions({ regenerate: true })}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const combined = result.combined || {
    meal_harmony_note: result.meal_harmony_note,
    recipes: result.recipes || [],
  };
  const individual = result.individual || [];
  const hasIndividualSections = individual.length > 0;
  const generatedTime = result.suggested_at
    ? new Date(result.suggested_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : null;

  return (
    <div className="suggestion-screen">
      {regenerating && (
        <div className="suggestion-regenerating-overlay">
          <LoadingSpinner variant="overlay" messages={GENERATION_MESSAGES} />
        </div>
      )}

      <header className="page-header suggestion-page-header desktop-only">
        <div className="page-header-row">
          <div>
            <h1 className="page-header-title">Today's recipes</h1>
            <StatsPills graphCount={result.graph_recipe_count} vectorCount={result.vector_chunk_count} />
          </div>
          <div className="page-header-actions">
            {result.from_cache && (
              <button
                type="button"
                className="btn-header-outline"
                disabled={regenerating}
                onClick={() => loadSuggestions({ regenerate: true })}
              >
                ↻ Regenerate
              </button>
            )}
            <button type="button" className="btn-header-outline" onClick={() => navigate(`/profile/${profileId}`)}>
              ↩ Back to Profile
            </button>
            <button type="button" className="btn-header-ghost" onClick={() => navigate(`/profile/${profileId}/history`)}>
              📜 View History
            </button>
          </div>
        </div>
      </header>

      <div className="suggestion-mobile-header mobile-only">
        <div className="suggestion-mobile-top">
          <BackButton onClick={() => navigate(`/profile/${profileId}`)} />
          <h1 className="suggestion-mobile-title">Today's recipes</h1>
          <button
            type="button"
            className="suggestion-mobile-history"
            onClick={() => navigate(`/profile/${profileId}/history`)}
          >
            📜 History
          </button>
        </div>
        <StatsPills graphCount={result.graph_recipe_count} vectorCount={result.vector_chunk_count} />
        {hasIndividualSections && (
          <SuggestionNavTabs
            activeTab={activeTab}
            people={individual}
            onSelect={scrollToSection}
          />
        )}
      </div>

      <div className="suggestion-scroll">
        {result.from_cache && (
          <div className="suggestion-cache-banner">
            <div className="suggestion-cache-banner-main">
              <span className="suggestion-cache-icon" aria-hidden="true">✓</span>
              <div>
                <div className="suggestion-cache-title">Saved for today</div>
                {generatedTime && (
                  <div className="suggestion-cache-time">Generated at {generatedTime}</div>
                )}
              </div>
            </div>
            <button
              type="button"
              className="suggestion-cache-regenerate mobile-only"
              disabled={regenerating}
              onClick={() => loadSuggestions({ regenerate: true })}
            >
              ↻ Regenerate
            </button>
          </div>
        )}
        {hasIndividualSections && (
          <SuggestionNavTabs
            activeTab={activeTab}
            people={individual}
            onSelect={scrollToSection}
            className="desktop-only"
          />
        )}
        <RecipeSection
          title={hasIndividualSections ? 'Cooking together' : "Today's recipes"}
          subtitle={hasIndividualSections ? 'One shared meal for everyone at the table' : null}
          note={combined.meal_harmony_note}
          recipes={combined.recipes}
          sectionKey="combined"
          sectionId="suggestion-combined"
          sectionRef={combinedRef}
          expandedRecipes={expandedRecipes}
          onToggleExpanded={toggleRecipeExpanded}
          favoriteKeys={favoriteKeys}
          onToggleFavorite={toggleFavorite}
        />

        {hasIndividualSections && (
          <div className="suggestion-individual-group">
            {individual.map((personSection) => (
              <RecipeSection
                key={personSection.person_name}
                title={`For ${personSection.person_name}`}
                subtitle="Individual meals tailored to this person"
                note={personSection.meal_note}
                recipes={personSection.recipes}
                sectionKey={`person-${personSection.person_name}`}
                sectionId={personSectionId(personSection.person_name)}
                expandedRecipes={expandedRecipes}
                onToggleExpanded={toggleRecipeExpanded}
                favoriteKeys={favoriteKeys}
                onToggleFavorite={toggleFavorite}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
