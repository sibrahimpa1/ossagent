import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import DoshaPill from '../components/DoshaPill';
import Modal from '../components/Modal';
import LoadingSpinner from '../components/LoadingSpinner';
import { splitDoshasForCard } from '../utils/doshas';
import { getLastCookedRecipe, getLastSuggestedRecipe } from '../utils/history';
import './HomeScreen.css';

export default function HomeScreen() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  useEffect(() => {
    loadProfiles();
  }, []);

  async function loadProfiles() {
    try {
      setLoading(true);
      const data = await api.getProfiles();
      const enriched = await Promise.all(
        data.map(async (profile) => {
          const [people, history] = await Promise.all([
            api.getPeople(profile.id).catch(() => []),
            api.getHistory(profile.id).catch(() => []),
          ]);
          const lastSuggested = getLastSuggestedRecipe(history);
          const lastCooked = getLastCookedRecipe(history);
          return { ...profile, people, lastSuggested, lastCooked };
        })
      );
      setProfiles(enriched);
    } catch (error) {
      console.error('Failed to load profiles:', error);
    } finally {
      setLoading(false);
    }
  }

  const filteredProfiles = useMemo(() => {
    if (!search.trim()) return profiles;
    const q = search.toLowerCase();
    return profiles.filter((p) =>
      p.name.toLowerCase().includes(q) ||
      p.people.some((person) => person.name.toLowerCase().includes(q))
    );
  }, [profiles, search]);

  async function handleCreateProfile() {
    if (!newProfileName.trim()) return;
    try {
      const profile = await api.createProfile(newProfileName);
      setNewProfileName('');
      setShowCreateModal(false);
      navigate(`/profile/${profile.id}`);
    } catch (error) {
      alert(`Failed to create profile: ${error.message}`);
    }
  }

  async function handleDeleteProfile(profileId) {
    try {
      await api.deleteProfile(profileId);
      setDeleteConfirm(null);
      loadProfiles();
    } catch (error) {
      alert(`Failed to delete profile: ${error.message}`);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div className="home-screen">
      <header className="home-hero mobile-only">
        <div className="home-hero-icon">🌿</div>
        <h1 className="home-title">
          Ayurvedalove<span className="home-dot">.</span>
        </h1>
        <p className="home-tagline">your ayurvedic kitchen companion</p>
      </header>

      <div className="home-quick-links mobile-only">
        <button type="button" className="btn-pill-link" onClick={() => navigate('/recipes')}>
          🍃 All Recipes
        </button>
        <button type="button" className="btn-pill-link" onClick={() => navigate('/recipes/new')}>
          ＋ New Recipe
        </button>
      </div>

      <header className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-header-title">Your tables</h1>
            <p className="page-header-sub">Pick a table to cook for today.</p>
          </div>
          <div className="page-header-actions">
            <label className="search-pill-desktop">
              <span>🔍</span>
              <input
                type="search"
                placeholder="Search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <button type="button" className="btn-header-cta" onClick={() => setShowCreateModal(true)}>
              ＋ New table
            </button>
          </div>
        </div>
      </header>

      <div className="home-content">
        <div className="section-label mobile-only">Your tables</div>

        <div className="tables-list">
          {filteredProfiles.map((profile) => (
            <div key={profile.id} className="table-card">
              <button
                type="button"
                className="table-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteConfirm(profile.id);
                }}
                title="Delete"
              >
                🗑
              </button>
              <div
                className="table-card-main"
                onClick={() => navigate(`/profile/${profile.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/profile/${profile.id}`)}
              >
                <div className="table-name">{profile.name}</div>
                {profile.people.length > 0 && (
                  <div className="table-people">
                    {profile.people.map((person) => {
                      const { primary, secondary } = splitDoshasForCard(person.doshas);
                      return (
                      <div key={person.id} className="table-person-row">
                        <span className="table-person-name">{person.name}</span>
                        <div className="table-person-doshas">
                          {primary.map((d) => (
                            <DoshaPill key={`p-${d.dosha}`} dosha={d.dosha} variant="filled" size="sm" tendency={d.tendency} />
                          ))}
                          {secondary.map((d) => (
                            <DoshaPill key={`s-${d.dosha}`} dosha={d.dosha} variant="imbalance" size="sm" tendency={d.tendency} />
                          ))}
                        </div>
                      </div>
                    );})}
                  </div>
                )}
                <div className="table-footer">
                  <span className="table-last-cooked">
                    {profile.lastCooked
                      ? `🍲 Last cooked · ${profile.lastCooked}`
                      : profile.lastSuggested
                        ? `✨ Last suggested · ${profile.lastSuggested}`
                        : `${profile.people_count} ${profile.people_count === 1 ? 'person' : 'people'}`}
                  </span>
                  <button
                    type="button"
                    className="table-history-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/profile/${profile.id}/history`);
                    }}
                  >
                    History →
                  </button>
                </div>
              </div>
            </div>
          ))}

          <button type="button" className="table-card-new" onClick={() => setShowCreateModal(true)}>
            <div className="new-profile-icon">+</div>
            <span className="mobile-only">New Profile</span>
            <span className="desktop-only">New table</span>
          </button>
        </div>
      </div>

      <Modal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} title="New table" maxWidth="420px">
        <div className="create-profile-form">
          <input
            type="text"
            className="form-field"
            placeholder="Table name (e.g., Home Table, Sunday Lunch)"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateProfile()}
            autoFocus
          />
          <div className="form-actions">
            <button type="button" className="btn-cta" onClick={handleCreateProfile} disabled={!newProfileName.trim()}>
              Create
            </button>
            <button type="button" className="form-cancel" onClick={() => setShowCreateModal(false)}>
              Cancel
            </button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={deleteConfirm !== null} onClose={() => setDeleteConfirm(null)} title="Delete table?" maxWidth="420px">
        <p className="confirm-text">This will permanently delete this table and all associated data.</p>
        <div className="form-actions">
          <button type="button" className="btn-cta btn-cta--danger" onClick={() => handleDeleteProfile(deleteConfirm)}>
            Delete
          </button>
          <button type="button" className="form-cancel" onClick={() => setDeleteConfirm(null)}>
            Cancel
          </button>
        </div>
      </Modal>
    </div>
  );
}
