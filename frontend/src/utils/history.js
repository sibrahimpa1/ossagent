/** Flatten recipes from new (combined + individual) or legacy response shape. */
export function getAllRecipesFromResponse(responseJson) {
  if (!responseJson) return [];

  const combined = responseJson.combined?.recipes || responseJson.recipes || [];
  const individual = (responseJson.individual || []).flatMap((section) => section.recipes || []);
  const seen = new Set();
  const all = [];

  for (const recipe of [...combined, ...individual]) {
    const name = recipe?.name;
    if (!name || seen.has(name)) continue;
    seen.add(name);
    all.push(recipe);
  }

  return all;
}

export function isRecipeCooked(session, recipeName) {
  return (session?.cooked_recipes || []).includes(recipeName);
}

/** True if any session on this day marked the recipe cooked. */
export function isRecipeCookedOnDay(sessions, recipeName) {
  return sessions.some((s) => isRecipeCooked(s, recipeName));
}

/** Newest session that contains this recipe (for toggling cooked state). */
export function getSessionForRecipe(sessions, recipeName) {
  const withCooked = sessions.find(
    (s) =>
      isRecipeCooked(s, recipeName) &&
      getAllRecipesFromResponse(s.response_json).some((r) => r.name === recipeName)
  );
  if (withCooked) return withCooked;
  return sessions.find((s) =>
    getAllRecipesFromResponse(s.response_json).some((r) => r.name === recipeName)
  );
}

function dayKey(dateString) {
  const d = new Date(dateString);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function isSameLocalDay(dateString, referenceDate = new Date()) {
  return dayKey(dateString) === dayKey(referenceDate.toISOString());
}

/** Newest suggestion session from today (history should be newest-first). */
export function getTodaySuggestion(history = []) {
  return history.find((session) => isSameLocalDay(session.suggested_at)) || null;
}

export function sessionToSuggestionResult(session) {
  if (!session?.response_json) return null;
  return {
    ...session.response_json,
    graph_recipe_count: session.graph_recipe_count,
    vector_chunk_count: session.vector_chunk_count,
    history_id: session.id,
    suggested_at: session.suggested_at,
    from_cache: true,
  };
}

function formatDayGroup(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);

  const isSameDay = (a, b) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (isSameDay(date, yesterday)) return 'Yesterday';
  if (isSameDay(date, now)) return 'Today';

  return date.toLocaleDateString('en-US', { weekday: 'long' });
}

function formatShortDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Group by day, one entry per recipe globally (newest day wins). */
export function buildDedupedHistoryGroups(history) {
  const groups = [];

  for (const session of history) {
    const key = dayKey(session.suggested_at);
    let group = groups.find((g) => g.dayKey === key);
    if (!group) {
      group = {
        dayKey: key,
        dayLabel: formatDayGroup(session.suggested_at),
        shortDate: formatShortDate(session.suggested_at),
        sessions: [],
        entries: [],
      };
      groups.push(group);
    }
    group.sessions.push(session);
  }

  const seenRecipes = new Set();

  for (const group of groups) {
    for (const session of group.sessions) {
      for (const recipe of getAllRecipesFromResponse(session.response_json)) {
        const name = recipe.name;
        if (!name || seenRecipes.has(name)) continue;
        seenRecipes.add(name);
        group.entries.push({
          recipeName: name,
          recipeKey: name,
          source: recipe.source || null,
          sessionId: session.id,
          peopleNames: session.people_snapshot?.map((p) => p.name).join(', ') || '',
          cooked: history.some((s) => isRecipeCooked(s, name)),
        });
      }
    }
  }

  return groups.filter((g) => g.entries.length > 0);
}

/** One entry per recipe name within a day (sessions newest-first). */
export function dedupeRecipesForDay(sessions) {
  const byName = new Map();

  for (const session of sessions) {
    for (const recipe of getAllRecipesFromResponse(session.response_json)) {
      const name = recipe.name;
      if (!name || byName.has(name)) continue;

      byName.set(name, {
        recipeName: name,
        sessionId: session.id,
        peopleNames: session.people_snapshot?.map((p) => p.name).join(', ') || '',
        cooked: isRecipeCookedOnDay(sessions, name),
      });
    }
  }

  return Array.from(byName.values());
}

/** Unique recent recipes across sessions (newest sessions first). */
export function dedupeRecentRecipes(sessions, limit = 3) {
  const items = [];
  const seen = new Set();

  for (const session of sessions) {
    for (const recipe of getAllRecipesFromResponse(session.response_json)) {
      const name = recipe.name;
      if (!name || seen.has(name)) continue;
      seen.add(name);
      items.push({
        id: session.id,
        recipe: name,
        session,
        cooked: isRecipeCooked(session, name),
      });
      if (items.length >= limit) return items;
    }
  }

  return items;
}

export function getLastSuggestedRecipe(history = []) {
  const recipes = getAllRecipesFromResponse(history[0]?.response_json);
  return recipes[0]?.name || null;
}

export function getLastCookedRecipe(history = []) {
  for (const session of history) {
    const cooked = session.cooked_recipes || [];
    if (cooked.length === 0) continue;
    const sessionRecipes = getAllRecipesFromResponse(session.response_json).map((r) => r.name);
    for (const name of sessionRecipes) {
      if (cooked.includes(name)) return name;
    }
    return cooked[cooked.length - 1];
  }
  return null;
}
