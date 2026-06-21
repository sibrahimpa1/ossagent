import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import BackButton from '../components/BackButton';
import LoadingSpinner from '../components/LoadingSpinner';
import RecipeDetailModal from '../components/RecipeDetailModal';
import { buildDedupedHistoryGroups, getSessionForRecipe } from '../utils/history';
import '../styles/recipe-row.css';
import './HistoryScreen.css';

function openRecipeDetail(setDetailRecipeKey, recipeKey) {
  setDetailRecipeKey(recipeKey);
}

function handleRowKeyDown(e, setDetailRecipeKey, recipeKey) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    openRecipeDetail(setDetailRecipeKey, recipeKey);
  }
}

export default function HistoryScreen() {
  const { profileId } = useParams();
  const navigate = useNavigate();

  const [profileName, setProfileName] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailRecipeKey, setDetailRecipeKey] = useState(null);

  useEffect(() => {
    loadHistory();
  }, [profileId]);

  async function loadHistory() {
    try {
      setLoading(true);
      const [historyData, profiles] = await Promise.all([
        api.getHistory(profileId),
        api.getProfiles(),
      ]);
      setHistory(historyData);
      const profile = profiles.find((p) => String(p.id) === String(profileId));
      setProfileName(profile?.name || 'Table');
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setLoading(false);
    }
  }

  async function toggleCooked(e, allHistory, recipeName) {
    e.stopPropagation();
    const session = getSessionForRecipe(allHistory, recipeName);
    if (!session) return;
    try {
      await api.toggleRecipeCooked(session.id, recipeName);
      loadHistory();
    } catch (error) {
      alert(`Failed to update: ${error.message}`);
    }
  }

  if (loading) return <LoadingSpinner message="Loading history..." />;

  const dayGroups = buildDedupedHistoryGroups(history);

  return (
    <div className="history-screen">
      <header className="history-top mobile-only">
        <BackButton onClick={() => navigate(`/profile/${profileId}`)} />
        <div>
          <h1 className="history-table-name">{profileName}</h1>
          <div className="history-subtitle">History</div>
        </div>
      </header>

      <header className="page-header desktop-only">
        <div className="page-header-row">
          <div>
            <h1 className="page-header-title">{profileName}</h1>
            <p className="page-header-sub">History · past suggestions & cooked meals</p>
          </div>
          <button type="button" className="btn-header-outline" onClick={() => navigate(`/profile/${profileId}`)}>
            ↩ Back to table
          </button>
        </div>
      </header>

        {history.length === 0 ? (
          <div className="history-empty">
            <p>No suggestions yet. Cook together to build your table history.</p>
            <button type="button" className="btn-cta" onClick={() => navigate(`/profile/${profileId}`)}>
              Get Started
            </button>
          </div>
        ) : (
          <div className="history-groups">
            {dayGroups.map((group) => (
              <div key={group.dayKey} className="history-day-group">
                <div className="history-day-header">
                  <span className="history-day-name">{group.dayLabel}</span>
                  <span className="history-day-date">· {group.shortDate}</span>
                </div>
                <div className="history-day-items recipe-row-list">
                  {group.entries.map((entry) => (
                    <div
                      key={entry.recipeName}
                      className="favorite-row favorite-row--clickable history-row"
                      role="button"
                      tabIndex={0}
                      onClick={() => openRecipeDetail(setDetailRecipeKey, entry.recipeKey)}
                      onKeyDown={(e) => handleRowKeyDown(e, setDetailRecipeKey, entry.recipeKey)}
                    >
                      <div className="history-row-body">
                        <div className="favorite-name">{entry.recipeName}</div>
                        <div className="favorite-source">
                          {entry.source
                            ? `📖 ${entry.source} · ${entry.cooked ? 'Cooked' : 'Suggested'} for ${entry.peopleNames}`
                            : `${entry.cooked ? 'Cooked' : 'Suggested'} · for ${entry.peopleNames}`}
                        </div>
                      </div>
                      <div className="history-row-actions">
                        <span className={`history-badge ${entry.cooked ? 'history-badge--cooked' : 'history-badge--suggested'}`}>
                          {entry.cooked ? '🍲 Cooked' : '✨ Suggested'}
                        </span>
                        <button
                          type="button"
                          className="history-mark-btn"
                          onClick={(e) => toggleCooked(e, history, entry.recipeName)}
                        >
                          {entry.cooked ? 'Undo' : 'Mark cooked'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

      <RecipeDetailModal
        isOpen={detailRecipeKey !== null}
        onClose={() => setDetailRecipeKey(null)}
        recipeKey={detailRecipeKey}
      />
    </div>
  );
}
