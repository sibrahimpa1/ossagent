import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/client';
import BackButton from '../components/BackButton';
import LoadingSpinner from '../components/LoadingSpinner';
import { DOSHA_IMBALANCE_OPTIONS, DOSHA_DOT, formatImbalance } from '../utils/imbalances';
import './RecipeFormScreen.css';

const DOSHAS = ['Vata', 'Pitta', 'Kapha'];

export default function RecipeFormScreen() {
  const navigate = useNavigate();
  const { recipeId } = useParams();
  const isEditing = Boolean(recipeId);

  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [source, setSource] = useState('');
  const [ingredients, setIngredients] = useState([]);
  const [ingredientInput, setIngredientInput] = useState('');
  const [methodNotes, setMethodNotes] = useState('');
  const [selectedDoshas, setSelectedDoshas] = useState([]);
  const [selectedImbalances, setSelectedImbalances] = useState([]);

  useEffect(() => {
    if (!isEditing) return;
    async function load() {
      try {
        const recipe = await api.getCustomRecipe(recipeId);
        setName(recipe.name);
        setSource(recipe.source || '');
        setIngredients(recipe.ingredients || []);
        setMethodNotes(recipe.method_notes || '');
        setSelectedDoshas(recipe.doshas || []);
        setSelectedImbalances(recipe.imbalances || []);
      } catch (error) {
        alert(`Failed to load recipe: ${error.message}`);
        navigate('/recipes');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [isEditing, recipeId, navigate]);

  function addIngredient() {
    const trimmed = ingredientInput.trim();
    if (!trimmed || ingredients.includes(trimmed)) return;
    setIngredients([...ingredients, trimmed]);
    setIngredientInput('');
  }

  function removeIngredient(item) {
    setIngredients(ingredients.filter((i) => i !== item));
  }

  function toggleDosha(dosha) {
    setSelectedDoshas((prev) =>
      prev.includes(dosha) ? prev.filter((d) => d !== dosha) : [...prev, dosha]
    );
  }

  function toggleImbalance(imbalance) {
    setSelectedImbalances((prev) =>
      prev.includes(imbalance) ? prev.filter((i) => i !== imbalance) : [...prev, imbalance]
    );
  }

  async function handleSave() {
    if (!name.trim()) {
      alert('Please enter a recipe name');
      return;
    }

    const payload = {
      name: name.trim(),
      source: source.trim() || null,
      ingredients,
      method_notes: methodNotes.trim() || null,
      doshas: selectedDoshas,
      imbalances: selectedImbalances,
    };

    try {
      setSaving(true);
      if (isEditing) {
        await api.updateCustomRecipe(recipeId, payload);
      } else {
        await api.createCustomRecipe(payload);
      }
      navigate('/recipes');
    } catch (error) {
      alert(`Failed to save recipe: ${error.message}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner message="Loading recipe..." />;

  return (
    <div className="recipe-form-screen">
      <header className="recipe-form-top mobile-only">
        <BackButton onClick={() => navigate('/recipes')} />
        <h1 className="recipe-form-title">{isEditing ? 'Edit Recipe' : 'New Recipe'}</h1>
      </header>

      <header className="page-header desktop-only">
        <div className="page-header-row">
          <div>
            <h1 className="page-header-title">{isEditing ? 'Edit Recipe' : 'New Recipe'}</h1>
            <p className="page-header-sub">Write a recipe from your own kitchen.</p>
          </div>
        </div>
      </header>

        <div className="recipe-form-body">
          <label className="field-label">Recipe name</label>
          <input
            type="text"
            className="form-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ana's Ginger Dal"
          />

          <label className="field-label">
            Source <span className="optional">· optional</span>
          </label>
          <input
            type="text"
            className="form-field form-field--body"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Grandma's notebook"
          />

          <label className="field-label">Ingredients</label>
          <div className="ingredient-tags">
            {ingredients.map((item) => (
              <span key={item} className="ingredient-tag-editable">
                {item}
                <button type="button" onClick={() => removeIngredient(item)} aria-label={`Remove ${item}`}>
                  ✕
                </button>
              </span>
            ))}
            <div className="ingredient-add-row">
              <input
                type="text"
                className="ingredient-add-input"
                value={ingredientInput}
                onChange={(e) => setIngredientInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addIngredient();
                  }
                }}
                placeholder="Add ingredient"
              />
              <button type="button" className="ingredient-add-btn" onClick={addIngredient}>
                ＋ Add
              </button>
            </div>
          </div>

          <label className="field-label">Method & notes</label>
          <textarea
            className="form-field form-field--textarea"
            value={methodNotes}
            onChange={(e) => setMethodNotes(e.target.value)}
            placeholder="Simmer lentils with ginger and cumin until soft..."
            rows={4}
          />

          <label className="field-label">
            Balances <span className="optional">· select doshas</span>
          </label>
          <div className="dosha-pill-row">
            {DOSHAS.map((dosha) => (
              <button
                key={dosha}
                type="button"
                className={`dosha-select-pill dosha-select-pill--${dosha.toLowerCase()} ${selectedDoshas.includes(dosha) ? 'selected' : ''}`}
                onClick={() => toggleDosha(dosha)}
              >
                {dosha}
              </button>
            ))}
          </div>

          <label className="field-label">
            Helps with <span className="optional">· select imbalances</span>
          </label>
          <p className="field-hint">Which dosha imbalances does this recipe support?</p>
          <div className="recipe-imbalance-groups">
            {DOSHAS.map((dosha) => (
              <div key={dosha} className="imbalance-group">
                <div className="imbalance-group-header">
                  <span className="imbalance-dot" style={{ background: DOSHA_DOT[dosha] }} />
                  {dosha}
                </div>
                <div className="imbalance-grid">
                  {DOSHA_IMBALANCE_OPTIONS[dosha].map((imbalance) => {
                    const checked = selectedImbalances.includes(imbalance);
                    return (
                      <button
                        key={imbalance}
                        type="button"
                        className="imbalance-option"
                        onClick={() => toggleImbalance(imbalance)}
                      >
                        <span
                          className={`imbalance-check ${checked ? 'checked' : ''}`}
                          style={checked ? { background: DOSHA_DOT[dosha] } : undefined}
                        >
                          {checked ? '✓' : ''}
                        </span>
                        <span>{formatImbalance(imbalance)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="recipe-form-actions">
          <button type="button" className="btn-cta" onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? 'Saving...' : 'Save recipe'}
          </button>
          <button type="button" className="form-cancel" onClick={() => navigate('/recipes')}>
            Cancel
          </button>
        </div>
    </div>
  );
}
