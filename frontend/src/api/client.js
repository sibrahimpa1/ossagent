/**
 * API client for backend communication
 */

const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? '/api' : 'http://localhost:8000');

class APIClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health
  async health() {
    return this.request('/health');
  }

  // Profiles
  async getProfiles() {
    return this.request('/profiles');
  }

  async createProfile(name) {
    return this.request('/profiles', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  }

  async deleteProfile(profileId) {
    return this.request(`/profiles/${profileId}`, {
      method: 'DELETE',
    });
  }

  // People
  async getPeople(profileId) {
    return this.request(`/profiles/${profileId}/people`);
  }

  async createPerson(profileId, personData) {
    return this.request(`/profiles/${profileId}/people`, {
      method: 'POST',
      body: JSON.stringify(personData),
    });
  }

  async updatePerson(personId, personData) {
    return this.request(`/people/${personId}`, {
      method: 'PUT',
      body: JSON.stringify(personData),
    });
  }

  async deletePerson(personId) {
    return this.request(`/people/${personId}`, {
      method: 'DELETE',
    });
  }

  // Suggestions
  async getSuggestions(profileId) {
    return this.request(`/profiles/${profileId}/suggest`, {
      method: 'POST',
    });
  }

  // History
  async getHistory(profileId) {
    return this.request(`/profiles/${profileId}/history`);
  }

  async toggleRecipeCooked(historyId, recipeName) {
    return this.request(`/history/${historyId}/cooked/toggle`, {
      method: 'POST',
      body: JSON.stringify({ recipe_name: recipeName }),
    });
  }

  // Recipes
  async getRecipes({ search, dosha, favoritesOnly } = {}) {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (dosha) params.set('dosha', dosha);
    if (favoritesOnly) params.set('favorites_only', 'true');
    const qs = params.toString();
    return this.request(`/recipes${qs ? `?${qs}` : ''}`);
  }

  async getRecipeDetail(recipeKey) {
    const params = new URLSearchParams({ key: recipeKey });
    return this.request(`/recipes/detail?${params.toString()}`);
  }

  async getFavoriteKeys() {
    return this.request('/recipes/favorites');
  }

  async toggleFavorite(recipeKey) {
    return this.request('/recipes/favorites/toggle', {
      method: 'POST',
      body: JSON.stringify({ recipe_key: recipeKey }),
    });
  }

  async createCustomRecipe(recipe) {
    return this.request('/recipes/custom', {
      method: 'POST',
      body: JSON.stringify(recipe),
    });
  }

  async getCustomRecipe(recipeId) {
    return this.request(`/recipes/custom/${recipeId}`);
  }

  async updateCustomRecipe(recipeId, recipe) {
    return this.request(`/recipes/custom/${recipeId}`, {
      method: 'PUT',
      body: JSON.stringify(recipe),
    });
  }

  async deleteCustomRecipe(recipeId) {
    return this.request(`/recipes/custom/${recipeId}`, {
      method: 'DELETE',
    });
  }
}

export default new APIClient();
