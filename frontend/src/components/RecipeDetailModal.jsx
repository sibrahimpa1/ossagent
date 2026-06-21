import { useEffect, useState } from 'react';
import api from '../api/client';
import Modal from './Modal';
import DoshaPill from './DoshaPill';
import RecipeMethod from './RecipeMethod';
import LoadingSpinner from './LoadingSpinner';
import FavoriteButton from './FavoriteButton';
import { parseRecipeText } from '../utils/parseRecipeText';
import { formatImbalance } from '../utils/imbalances';
import './RecipeDetailModal.css';

export default function RecipeDetailModal({
  isOpen,
  onClose,
  recipeKey,
  onFavoriteToggle,
}) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !recipeKey) {
      setDetail(null);
      setError(null);
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getRecipeDetail(recipeKey);
        if (!cancelled) {
          setDetail(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Failed to load recipe');
          setDetail(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [isOpen, recipeKey]);

  async function handleToggleFavorite() {
    if (!detail) return;
    try {
      const result = await api.toggleFavorite(detail.recipe_key);
      setDetail((prev) => (prev ? { ...prev, is_favorited: result.is_favorited } : prev));
      onFavoriteToggle?.(result);
    } catch (err) {
      alert(`Failed to update favorite: ${err.message}`);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={detail?.name || 'Recipe'}
      maxWidth="560px"
    >
      {loading && (
        <div className="recipe-detail-loading">
          <LoadingSpinner />
        </div>
      )}

      {!loading && error && (
        <p className="recipe-detail-error">{error}</p>
      )}

      {!loading && !error && detail && (() => {
        const parsedMethod = detail.method_notes ? parseRecipeText(detail.method_notes) : null;
        const showGraphIngredients =
          detail.ingredients?.length > 0 &&
          !(parsedMethod?.ingredients?.length > 0);

        return (
        <div className="recipe-detail">
          <div className="recipe-detail-header">
            <div className="recipe-detail-source">
              {detail.is_custom ? '✍️ Written by you' : `📖 ${detail.source || 'Ayurvedic cookbook'}`}
            </div>
            <FavoriteButton
              active={detail.is_favorited}
              size="lg"
              onClick={handleToggleFavorite}
            />
          </div>

          {(detail.doshas?.length > 0 || detail.imbalances?.length > 0) && (
            <div className="recipe-detail-tags">
              {detail.doshas?.map((dosha) => (
                <DoshaPill key={dosha} dosha={dosha} size="sm" />
              ))}
              {detail.imbalances?.map((imbalance) => (
                <span key={imbalance} className="recipe-detail-imbalance-tag">
                  {formatImbalance(imbalance)}
                </span>
              ))}
            </div>
          )}

          {showGraphIngredients && (
            <section className="recipe-detail-section">
              <h3 className="recipe-detail-section-title">Ingredients</h3>
              <ul className="recipe-detail-ingredients">
                {detail.ingredients.map((ingredient) => (
                  <li key={ingredient}>{ingredient}</li>
                ))}
              </ul>
            </section>
          )}

          {detail.method_notes ? (
            <section className="recipe-detail-section recipe-detail-section--method">
              <h3 className="recipe-detail-section-title">Recipe</h3>
              <RecipeMethod text={detail.method_notes} />
            </section>
          ) : (
            <p className="recipe-detail-empty">
              Full recipe instructions aren&apos;t available for this entry yet.
            </p>
          )}
        </div>
        );
      })()}
    </Modal>
  );
}
