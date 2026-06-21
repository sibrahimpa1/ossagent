import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import BackButton from '../components/BackButton';
import DoshaPill from '../components/DoshaPill';
import Modal from '../components/Modal';
import RecipeDetailModal from '../components/RecipeDetailModal';
import LoadingSpinner from '../components/LoadingSpinner';
import FavoriteButton from '../components/FavoriteButton';
import HeartIcon from '../components/HeartIcon';
import { splitDoshasForCard, buildTendencyMap, DOSHA_TENDENCY_OPTIONS } from '../utils/doshas';
import { DOSHA_IMBALANCE_OPTIONS, DOSHA_DOT, formatImbalance } from '../utils/imbalances';
import { dedupeRecipesForDay, getSessionForRecipe, dedupeRecentRecipes, getTodaySuggestion } from '../utils/history';
import './ProfileScreen.css';
import '../styles/recipe-row.css';

const DOSHAS = ['Vata', 'Pitta', 'Kapha'];
const IMBALANCES = DOSHA_IMBALANCE_OPTIONS;

function DoshaTendencyPicker({ doshas, tendencies, onChange, excessOnly = false }) {
  if (!doshas.length) return null;

  const options = excessOnly
    ? DOSHA_TENDENCY_OPTIONS.filter((option) => option.value === 'excess')
    : DOSHA_TENDENCY_OPTIONS;

  return (
    <div className="dosha-expression-panel">
      <div className="dosha-expression-heading">
        <span className="dosha-expression-title">Current expression</span>
        <span className="dosha-expression-optional">· optional</span>
      </div>

      <div className="dosha-expression-rows">
        {doshas.map((dosha) => (
          <div key={dosha} className="dosha-expression-row">
            <span className={`dosha-expression-badge dosha-expression-badge--${dosha.toLowerCase()}`}>
              {dosha}
            </span>

            {excessOnly ? (
              <button
                type="button"
                className={`dosha-expression-single${tendencies[dosha] === 'excess' ? ' selected' : ''}`}
                onClick={() => onChange(dosha, tendencies[dosha] === 'excess' ? null : 'excess')}
              >
                Excess
              </button>
            ) : (
              <div className="dosha-expression-segment" role="group" aria-label={`${dosha} expression`}>
                {options.map((option) => {
                  const isSelected = tendencies[dosha] === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      className={`dosha-expression-option${isSelected ? ' selected' : ''}`}
                      onClick={() => onChange(dosha, isSelected ? null : option.value)}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ProfileScreen() {
  const { profileId } = useParams();
  const navigate = useNavigate();

  const [profileName, setProfileName] = useState('');
  const [people, setPeople] = useState([]);
  const [history, setHistory] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPersonModal, setShowPersonModal] = useState(false);
  const [editingPerson, setEditingPerson] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [detailRecipeKey, setDetailRecipeKey] = useState(null);

  const [personName, setPersonName] = useState('');
  const [primaryDoshas, setPrimaryDoshas] = useState([]);
  const [secondaryDoshas, setSecondaryDoshas] = useState([]);
  const [primaryTendencies, setPrimaryTendencies] = useState({});
  const [imbalanceTendencies, setImbalanceTendencies] = useState({});
  const [selectedImbalances, setSelectedImbalances] = useState([]);

  useEffect(() => {
    loadData();
  }, [profileId]);

  async function loadData() {
    try {
      setLoading(true);
      const [peopleData, historyData, profiles, favoritesData] = await Promise.all([
        api.getPeople(profileId),
        api.getHistory(profileId).catch(() => []),
        api.getProfiles(),
        api.getRecipes({ favoritesOnly: true }).catch(() => []),
      ]);
      setPeople(peopleData);
      setHistory(historyData);
      setFavorites(favoritesData.slice(0, 2));
      const profile = profiles.find((p) => String(p.id) === String(profileId));
      setProfileName(profile?.name || 'Table');
    } catch (error) {
      console.error('Failed to load profile:', error);
    } finally {
      setLoading(false);
    }
  }

  function openAddPersonModal() {
    setEditingPerson(null);
    setPersonName('');
    setPrimaryDoshas([]);
    setSecondaryDoshas([]);
    setPrimaryTendencies({});
    setImbalanceTendencies({});
    setSelectedImbalances([]);
    setShowPersonModal(true);
  }

  function openEditPersonModal(person) {
    setEditingPerson(person);
    setPersonName(person.name);
    setPrimaryDoshas([...new Set(person.doshas.filter((d) => d.is_primary).map((d) => d.dosha))]);
    setSecondaryDoshas([...new Set(person.doshas.filter((d) => !d.is_primary).map((d) => d.dosha))]);
    setPrimaryTendencies(buildTendencyMap(person.doshas, true));
    const imbalanceMap = buildTendencyMap(person.doshas, false);
    Object.keys(imbalanceMap).forEach((dosha) => {
      if (imbalanceMap[dosha] !== 'excess') imbalanceMap[dosha] = null;
    });
    setImbalanceTendencies(imbalanceMap);
    setSelectedImbalances(person.imbalances);
    setShowPersonModal(true);
  }

  async function handleSavePerson() {
    if (!personName.trim() || primaryDoshas.length === 0) {
      alert('Please enter a name and select at least one primary dosha');
      return;
    }

    const doshasForApi = [
      ...primaryDoshas.map((dosha) => ({
        dosha,
        is_primary: true,
        tendency: primaryTendencies[dosha] || null,
      })),
      ...secondaryDoshas.map((dosha) => ({
        dosha,
        is_primary: false,
        tendency: imbalanceTendencies[dosha] === 'excess' ? 'excess' : null,
      })),
    ];

    const personData = {
      name: personName,
      doshas: doshasForApi,
      imbalances: selectedImbalances,
    };

    try {
      if (editingPerson) {
        await api.updatePerson(editingPerson.id, personData);
      } else {
        await api.createPerson(profileId, personData);
      }
      setShowPersonModal(false);
      loadData();
    } catch (error) {
      alert(`Failed to save person: ${error.message}`);
    }
  }

  async function handleDeletePerson(personId) {
    try {
      await api.deletePerson(personId);
      setDeleteConfirm(null);
      loadData();
    } catch (error) {
      alert(`Failed to delete person: ${error.message}`);
    }
  }

  function togglePrimary(dosha) {
    setPrimaryDoshas((prev) => {
      if (prev.includes(dosha)) {
        setPrimaryTendencies((current) => {
          const next = { ...current };
          delete next[dosha];
          return next;
        });
        return prev.filter((d) => d !== dosha);
      }
      return [...prev, dosha];
    });
  }

  function toggleSecondary(dosha) {
    setSecondaryDoshas((prev) => {
      if (prev.includes(dosha)) {
        setImbalanceTendencies((current) => {
          const next = { ...current };
          delete next[dosha];
          return next;
        });
        return prev.filter((d) => d !== dosha);
      }
      return [...prev, dosha];
    });
  }

  function setPrimaryTendency(dosha, tendency) {
    setPrimaryTendencies((prev) => ({ ...prev, [dosha]: tendency }));
  }

  function setImbalanceTendency(dosha, tendency) {
    setImbalanceTendencies((prev) => ({ ...prev, [dosha]: tendency }));
  }

  function toggleImbalance(imbalance) {
    setSelectedImbalances((prev) =>
      prev.includes(imbalance) ? prev.filter((i) => i !== imbalance) : [...prev, imbalance]
    );
  }

  async function toggleFavorite(recipeKey) {
    try {
      await api.toggleFavorite(recipeKey);
      loadData();
    } catch (error) {
      alert(`Failed to update favorite: ${error.message}`);
    }
  }

  async function toggleCooked(sessions, recipeName) {
    const session = getSessionForRecipe(sessions, recipeName);
    if (!session) return;
    try {
      await api.toggleRecipeCooked(session.id, recipeName);
      loadData();
    } catch (error) {
      alert(`Failed to update: ${error.message}`);
    }
  }

  const todaySuggestion = getTodaySuggestion(history);
  const suggestCtaLabel = people.length === 0
    ? 'Add at least one person'
    : todaySuggestion
      ? "✨ View Today's Recipes"
      : "✨ Get Today's Recipes";

  const newestSession = history[0];
  const daySessions = newestSession
    ? history.filter((session) => {
        const a = new Date(session.suggested_at);
        const b = new Date(newestSession.suggested_at);
        return (
          a.getFullYear() === b.getFullYear() &&
          a.getMonth() === b.getMonth() &&
          a.getDate() === b.getDate()
        );
      })
    : [];

  const cardDate = newestSession ? new Date(newestSession.suggested_at) : new Date();
  const dayLabel = cardDate.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();
  const dateLabel = cardDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }).toUpperCase();

  const historyCards = dedupeRecipesForDay(daySessions).slice(0, 3).map((entry) => ({
    ...entry,
    recipe: entry.recipeName,
    dayLabel,
    dateLabel,
    sessions: daySessions,
  }));

  const historyPreview = dedupeRecentRecipes(history, 2).map((entry) => {
    const date = new Date(entry.session.suggested_at);
    const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `${label} · ${entry.recipe} ${entry.cooked ? '🍲' : '✨'}`;
  });

  if (loading) return <LoadingSpinner />;

  return (
    <div className="profile-screen">
      <div className="profile-layout">
        <div className="profile-main">
          <header className="profile-top mobile-only">
            <BackButton onClick={() => navigate('/')} />
            <h1 className="profile-title">
              {profileName} <span className="profile-edit-icon">✎</span>
            </h1>
          </header>

          <header className="page-header desktop-only">
            <div className="page-header-row">
              <div>
                <h1 className="page-header-title">{profileName}</h1>
                <p className="page-header-sub">
                  {people.length} {people.length === 1 ? 'person' : 'people'} cooking today
                </p>
              </div>
              <button type="button" className="btn-header-outline" onClick={() => navigate('/')}>
                ↩ All tables
              </button>
            </div>
          </header>

          <div className="history-preview-card mobile-only" role="button" tabIndex={0} onClick={() => navigate(`/profile/${profileId}/history`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/profile/${profileId}/history`)}>
            <div className="history-preview-header">
              <div className="history-preview-left">
                <span className="history-preview-icon">📜</span>
                <div>
                  <div className="history-preview-title">Table history</div>
                  <div className="history-preview-sub">Past days · what we suggested & cooked</div>
                </div>
              </div>
              <span className="history-preview-arrow">→</span>
            </div>
            {historyPreview.length > 0 && (
              <div className="history-preview-chips">
                {historyPreview.map((chip, i) => (
                  <span key={i} className="history-chip">{chip}</span>
                ))}
              </div>
            )}
          </div>

          <div className="history-desktop desktop-only">
            <div className="history-desktop-header">
              <span className="section-label">📜 Table history</span>
              <button type="button" className="favorites-see-all" onClick={() => navigate(`/profile/${profileId}/history`)}>
                View all →
              </button>
            </div>
            {historyCards.length > 0 ? (
              <div className="history-desktop-cards">
                {historyCards.map((card) => (
                  <div key={card.recipeName} className="history-desktop-card">
                    <div className="history-desktop-date">{card.dayLabel} · {card.dateLabel}</div>
                    <div className="history-desktop-recipe">{card.recipe}</div>
                    <div className="history-desktop-actions">
                      <span className={`history-desktop-badge ${card.cooked ? 'history-desktop-badge--cooked' : 'history-desktop-badge--suggested'}`}>
                        {card.cooked ? '🍲 Cooked' : '✨ Suggested'}
                      </span>
                      <button
                        type="button"
                        className="history-mark-btn"
                        onClick={() => toggleCooked(card.sessions, card.recipeName)}
                      >
                        {card.cooked ? 'Undo cooked' : 'Mark cooked'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="favorites-empty">No history yet — get your first suggestions.</div>
            )}
          </div>

          <div className="section-label">People cooking today</div>

        {people.length === 0 ? (
          <div className="people-empty">No one added yet</div>
        ) : (
          <div className="people-row">
            {people.map((person) => {
              const { primary, secondary } = splitDoshasForCard(person.doshas);

              return (
                <div
                  key={person.id}
                  className="person-card"
                  onClick={() => openEditPersonModal(person)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && openEditPersonModal(person)}
                >
                  <div className="person-card-header">
                    <div className="person-card-name">{person.name}</div>
                    <span className="person-edit-icon desktop-only">✎</span>
                  </div>
                  <div className="person-doshas">
                    {primary.map((d) => (
                      <DoshaPill key={d.dosha} dosha={d.dosha} variant="filled" size="lg" tendency={d.tendency} />
                    ))}
                    {secondary.map((d) => (
                      <DoshaPill key={d.dosha} dosha={d.dosha} variant="imbalance" size="sm" tendency={d.tendency} />
                    ))}
                  </div>
                  {person.imbalances.length > 0 && (
                    <div className="person-imbalances">
                      {person.imbalances.map((imb, i) => (
                        <span key={i} className="imbalance-tag">{formatImbalance(imb)}</span>
                      ))}
                    </div>
                  )}
                  <button
                    type="button"
                    className="person-delete mobile-only"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(person.id);
                    }}
                  >
                    Remove
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <button type="button" className="btn-outline add-person-btn" onClick={openAddPersonModal}>
          <span>👤</span> Add person
        </button>

        <div className="favorites-header">
          <span className="section-label favorites-label">
            <HeartIcon filled size={13} className="favorites-heart" /> This table's favorites
          </span>
          <button type="button" className="favorites-see-all" onClick={() => navigate('/recipes?filter=favorites')}>
            See all
          </button>
        </div>
        <div className="favorites-list recipe-row-list">
          {favorites.length > 0 ? favorites.map((recipe) => (
            <div
              key={recipe.recipe_key}
              className="favorite-row favorite-row--clickable"
              role="button"
              tabIndex={0}
              onClick={() => setDetailRecipeKey(recipe.recipe_key)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setDetailRecipeKey(recipe.recipe_key);
                }
              }}
            >
              <div>
                <div className="favorite-name">{recipe.name}</div>
                <div className="favorite-source">
                  {recipe.is_custom ? '✍️ Written by you' : `📖 ${recipe.source}`}
                </div>
              </div>
              <FavoriteButton
                active
                size="sm"
                aria-label="Remove from favorites"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleFavorite(recipe.recipe_key);
                }}
              />
            </div>
          )) : (
            <div className="favorites-empty">Save recipes with the heart icon to build favorites</div>
          )}
        </div>

        <div className="profile-cta-wrap mobile-only">
          <button
            type="button"
            className="btn-cta"
            disabled={people.length === 0}
            onClick={() => navigate(`/profile/${profileId}/suggest`)}
          >
            {suggestCtaLabel}
          </button>
        </div>
        </div>

        <aside className="profile-rail desktop-only">
          <div className="profile-rail-card">
            <div className="section-label">Cooking today</div>
            {people.length > 0 && (
              <p className="profile-rail-meta">
                {people.length} {people.length === 1 ? 'person' : 'people'} · table servings
              </p>
            )}
            {people.length === 0 ? (
              <p className="profile-rail-empty">Add people to start cooking.</p>
            ) : (
              <div className="profile-rail-people">
                {people.map((person) => (
                  <div key={person.id} className="profile-rail-person">
                    <div className="profile-rail-avatar">{person.name[0]}</div>
                    <span className="profile-rail-name">{person.name}</span>
                  </div>
                ))}
              </div>
            )}
            <button
              type="button"
              className="btn-cta profile-rail-cta"
              disabled={people.length === 0}
              onClick={() => navigate(`/profile/${profileId}/suggest`)}
            >
              {suggestCtaLabel}
            </button>
          </div>
        </aside>
      </div>

      <Modal
        isOpen={showPersonModal}
        onClose={() => setShowPersonModal(false)}
        title={editingPerson ? 'Edit Person' : 'Add Person'}
        variant="bottom-sheet"
      >
        <div className="person-form">
          <input
            type="text"
            className="form-field"
            value={personName}
            onChange={(e) => setPersonName(e.target.value)}
            placeholder="Name"
            autoFocus
          />

          <div className="dosha-section-label">Primary Dosha · select all that apply</div>
          <div className="dosha-pill-row">
            {DOSHAS.map((dosha) => (
              <button
                key={dosha}
                type="button"
                className={`dosha-select-pill dosha-select-pill--${dosha.toLowerCase()} ${primaryDoshas.includes(dosha) ? 'selected' : ''}`}
                onClick={() => togglePrimary(dosha)}
              >
                {dosha}
              </button>
            ))}
          </div>

          <DoshaTendencyPicker
            doshas={primaryDoshas}
            tendencies={primaryTendencies}
            onChange={setPrimaryTendency}
          />

          <div className="dosha-section-label">
            Imbalance Dosha <span className="optional">· secondary, optional</span>
          </div>
          <p className="dosha-section-hint">Doshas currently out of balance — can overlap with primary (e.g. Pitta primary with Pitta imbalance).</p>
          <div className="dosha-pill-row dosha-pill-row--secondary">
            {DOSHAS.map((dosha) => {
              const isSelected = secondaryDoshas.includes(dosha);
              return (
                <button
                  key={dosha}
                  type="button"
                  className={`dosha-select-pill dosha-select-pill--${dosha.toLowerCase()} dosha-select-pill--sm dosha-select-pill--imbalance ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleSecondary(dosha)}
                >
                  {dosha}
                </button>
              );
            })}
          </div>

          <DoshaTendencyPicker
            doshas={secondaryDoshas}
            tendencies={imbalanceTendencies}
            onChange={setImbalanceTendency}
            excessOnly
          />

          <div className="dosha-section-label">Current Imbalances</div>
          {DOSHAS.map((dosha) => (
            <div key={dosha} className="imbalance-group">
              <div className="imbalance-group-header">
                <span className="imbalance-dot" style={{ background: DOSHA_DOT[dosha] }} />
                <span>{dosha}</span>
              </div>
              <div className="imbalance-grid">
                {IMBALANCES[dosha].map((imbalance) => {
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
                        style={checked ? { background: DOSHA_DOT[dosha], borderColor: DOSHA_DOT[dosha] } : {}}
                      >
                        {checked && '✓'}
                      </span>
                      <span>{formatImbalance(imbalance)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="person-form-actions">
            <button type="button" className="btn-cta" onClick={handleSavePerson} disabled={!personName.trim() || primaryDoshas.length === 0}>
              Save
            </button>
            <button type="button" className="form-cancel" onClick={() => setShowPersonModal(false)}>
              Cancel
            </button>
          </div>
        </div>
      </Modal>

      <RecipeDetailModal
        isOpen={detailRecipeKey !== null}
        onClose={() => setDetailRecipeKey(null)}
        recipeKey={detailRecipeKey}
        onFavoriteToggle={() => loadData()}
      />

      <Modal
        isOpen={deleteConfirm !== null}
        onClose={() => setDeleteConfirm(null)}
        title="Remove person?"
        maxWidth="390px"
      >
        <p className="confirm-text">Remove this person from the table?</p>
        <div className="form-actions">
          <button type="button" className="btn-cta btn-cta--danger" onClick={() => handleDeletePerson(deleteConfirm)}>
            Remove
          </button>
          <button type="button" className="form-cancel" onClick={() => setDeleteConfirm(null)}>
            Cancel
          </button>
        </div>
      </Modal>
    </div>
  );
}
