/** Unique doshas for display (handles duplicate assignments). */
export function uniqueDoshas(doshas = []) {
  const seen = new Set();
  return doshas.filter((d) => {
    if (seen.has(d.dosha)) return false;
    seen.add(d.dosha);
    return true;
  });
}

export const DOSHA_TENDENCY_OPTIONS = [
  { value: 'excess', label: 'Excess', shortLabel: 'High', hint: 'Too much energy' },
  { value: 'deficiency', label: 'Deficiency', shortLabel: 'Low', hint: 'Too little energy' },
];

export function tendencyLabel(tendency, { short = false } = {}) {
  const option = DOSHA_TENDENCY_OPTIONS.find((item) => item.value === tendency);
  if (!option) return null;
  return short ? option.shortLabel : option.label;
}

export function buildTendencyMap(doshas = [], isPrimary) {
  const map = {};
  for (const entry of doshas) {
    if (Boolean(entry.is_primary) !== isPrimary) continue;
    if (map[entry.dosha] === undefined) {
      map[entry.dosha] = entry.tendency || null;
    }
  }
  return map;
}

export function splitDoshasForCard(doshas = []) {
  if (!doshas.length) return { primary: [], secondary: [], all: [] };

  const seenPrimary = new Set();
  const seenSecondary = new Set();
  const primary = [];
  const secondary = [];

  for (const d of doshas) {
    if (d.is_primary) {
      if (!seenPrimary.has(d.dosha)) {
        seenPrimary.add(d.dosha);
        primary.push(d);
      }
    } else if (!seenSecondary.has(d.dosha)) {
      seenSecondary.add(d.dosha);
      secondary.push(d);
    }
  }

  return { primary, secondary, all: doshas };
}
