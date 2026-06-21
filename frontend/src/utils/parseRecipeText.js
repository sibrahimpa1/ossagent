const META_LINE = /^(TASTES|PREP TIME|COOK TIME|SEASON|SERVINGS)\s*:?\s*(.*)$/i;
const PREP_COOK_COMBO = /^PREP TIME:\s*(.+?)\s*\/\s*COOK TIME:\s*(.+)$/i;
const DOSHA_NOTE = /^(Vatas|Pittas|Kaphas)\s+(can|should|may|will benefit|need|do well|might)/i;
const TIP_LINE = /^(Timesaving Tip|Chef['']s Tip|Tip|Note):\s*(.+)$/i;
const STEP_LINE = /^(?:Step\s*)?(\d+)[.:)]\s*(.+)$/i;
const WHAT_YOU_NEED = /^What you need:?$/i;
const WHAT_TO_DO = /^What to do:?$/i;
const SERVINGS_COUNT = /^(\d+[–\-]?\d*)\s*$/;
const LONE_DOSHA = /^(Vata|Pitta|Kapha|VATA|PITTA|KAPHA)$/i;
const LONE_SERVINGS = /^SERVINGS?$/i;

const QUANTITY_INGREDIENT =
  /^([\d¼½¾⅓⅔⅛⅜⅝⅞./]+(?:\s+or\s+[\d¼½¾]+)?|\.\d+)\s+.+/i;

const FRACTION_START = /^[¼½¾⅓⅔⅛⅜⅝⅞]/;

function isIngredientLine(line) {
  if (STEP_LINE.test(line)) return false;
  if (META_LINE.test(line)) return false;
  if (DOSHA_NOTE.test(line)) return false;
  if (TIP_LINE.test(line)) return false;
  if (WHAT_YOU_NEED.test(line) || WHAT_TO_DO.test(line)) return false;
  if (LONE_DOSHA.test(line) || LONE_SERVINGS.test(line)) return false;
  if (line.length > 120) return false;
  if (/^\d+\s+(?:minutes?|hours?|seconds?|mins?)\.?\s*$/i.test(line)) return false;

  return QUANTITY_INGREDIENT.test(line) || FRACTION_START.test(line);
}

function isTitleLine(line) {
  if (line.length > 60) return false;
  if (/[a-z]/.test(line)) return false;
  if (META_LINE.test(line)) return false;
  if (STEP_LINE.test(line)) return false;
  if (LONE_DOSHA.test(line) || LONE_SERVINGS.test(line)) return false;
  return /^[A-Z0-9][A-Z0-9\s\-–—&,'']+$/.test(line);
}

function isParagraphLine(line) {
  if (line.length < 50) return false;
  if (!/^[A-Z"'(]/.test(line)) return false;
  if (/^[A-Z\s]{8,}$/.test(line)) return false;
  return /[a-z]/.test(line) && !STEP_LINE.test(line) && !isIngredientLine(line);
}

function isContinuationLine(line) {
  if (STEP_LINE.test(line)) return false;
  if (META_LINE.test(line)) return false;
  if (WHAT_YOU_NEED.test(line) || WHAT_TO_DO.test(line)) return false;
  if (isTitleLine(line)) return false;
  if (line.length <= 40 && /^(\d+\s+(?:minutes?|hours?|seconds?|mins?)|and\b)/i.test(line)) {
    return true;
  }
  if (isIngredientLine(line)) return false;
  return /^[a-z("'’/]/.test(line) || /^[^A-Z0-9]/.test(line);
}

function isHardBoundaryLine(line) {
  return (
    META_LINE.test(line) ||
    PREP_COOK_COMBO.test(line) ||
    STEP_LINE.test(line) ||
    TIP_LINE.test(line) ||
    DOSHA_NOTE.test(line) ||
    WHAT_YOU_NEED.test(line) ||
    WHAT_TO_DO.test(line) ||
    isTitleLine(line) ||
    isIngredientLine(line) ||
    LONE_DOSHA.test(line) ||
    LONE_SERVINGS.test(line) ||
    SERVINGS_COUNT.test(line)
  );
}

function normalizeWrappedLines(lines) {
  const result = [];

  for (const line of lines) {
    if (result.length === 0) {
      result.push(line);
      continue;
    }

    const prev = result[result.length - 1];

    if (isHardBoundaryLine(line) || isHardBoundaryLine(prev)) {
      result.push(line);
      continue;
    }

    const prevIncomplete = !/[.!?]["']?\s*$/.test(prev);
    const shouldJoin =
      isContinuationLine(line) ||
      (prevIncomplete && line.length < 100);

    if (shouldJoin) {
      result[result.length - 1] = `${prev} ${line}`;
    } else {
      result.push(line);
    }
  }

  return result;
}

function appendContinuation(target, line) {
  if (!target.length || !isContinuationLine(line)) return false;
  target[target.length - 1] = `${target[target.length - 1]} ${line}`;
  return true;
}

function pushMeta(meta, key, value) {
  if (!value?.trim()) return;
  const existing = meta.find((item) => item.key === key);
  if (existing) return;
  meta.push({ key, value: value.trim() });
}

function parseMetaLine(line, meta) {
  const combo = line.match(PREP_COOK_COMBO);
  if (combo) {
    pushMeta(meta, 'prep', combo[1].trim());
    pushMeta(meta, 'cook', combo[2].trim());
    return 'prep';
  }

  const match = line.match(META_LINE);
  if (!match) return false;

  const label = match[1].toLowerCase();
  const value = match[2]?.trim();

  if (label === 'tastes') pushMeta(meta, 'tastes', value);
  else if (label === 'prep time') pushMeta(meta, 'prep', value);
  else if (label === 'cook time') pushMeta(meta, 'cook', value);
  else if (label === 'season') pushMeta(meta, 'season', value);
  else if (label === 'servings') pushMeta(meta, 'servings', value);
  return label === 'prep time' || label === 'cook time' ? 'prep' : true;
}

export function parseRecipeText(text) {
  if (!text?.trim()) {
    return { meta: [], doshaNotes: [], tips: [], paragraphs: [], ingredients: [], steps: [], summary: null };
  }

  const lines = normalizeWrappedLines(
    text
      .split(/\n/)
      .map((line) => line.trim())
      .filter(Boolean),
  );

  const meta = [];
  const doshaNotes = [];
  const tips = [];
  const paragraphs = [];
  const ingredients = [];
  const steps = [];
  let summary = null;

  let mode = 'scan';
  let pendingServings = null;
  let titleBuffer = [];
  let seenPrepMeta = false;
  let skipPreambleBlock = false;

  function flushTitleBuffer() {
    titleBuffer = [];
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (skipPreambleBlock) {
      if (isHardBoundaryLine(line) && !isContinuationLine(line)) {
        skipPreambleBlock = false;
      } else {
        continue;
      }
    }

    if (LONE_DOSHA.test(line)) continue;

    if (SERVINGS_COUNT.test(line)) {
      pendingServings = line.match(SERVINGS_COUNT)[1];
      continue;
    }

    if (LONE_SERVINGS.test(line) && pendingServings) {
      pushMeta(meta, 'servings', pendingServings);
      pendingServings = null;
      continue;
    }

    if (WHAT_YOU_NEED.test(line)) {
      flushTitleBuffer();
      mode = 'ingredients';
      continue;
    }

    if (WHAT_TO_DO.test(line)) {
      flushTitleBuffer();
      mode = 'steps';
      continue;
    }

    const stepMatch = line.match(STEP_LINE);
    if (stepMatch) {
      flushTitleBuffer();
      mode = 'steps';
      steps.push({ number: Number(stepMatch[1]), text: stepMatch[2].trim() });
      continue;
    }

    if (parseMetaLine(line, meta)) {
      flushTitleBuffer();
      if (line.includes('PREP TIME') || line.includes('COOK TIME')) {
        seenPrepMeta = true;
      }
      continue;
    }

    if (isTitleLine(line)) {
      titleBuffer.push(line);
      continue;
    }

    if (titleBuffer.length > 0) {
      flushTitleBuffer();
    }

    const tipMatch = line.match(TIP_LINE);
    if (tipMatch) {
      if (seenPrepMeta) {
        tips.push(tipMatch[2] ? `${tipMatch[1]}: ${tipMatch[2]}` : line);
      } else {
        skipPreambleBlock = true;
      }
      continue;
    }

    if (DOSHA_NOTE.test(line)) {
      doshaNotes.push(line);
      continue;
    }

    if (isParagraphLine(line) && seenPrepMeta) {
      if (steps.length > 0) {
        summary = summary ? `${summary} ${line}` : line;
      } else if (mode !== 'ingredients' && mode !== 'steps') {
        paragraphs.push(line);
      }
      mode = 'scan';
      continue;
    }

    if (mode === 'ingredients' || (mode === 'scan' && isIngredientLine(line))) {
      if (mode === 'scan') mode = 'ingredients';
      ingredients.push(line.replace(/,\s*$/, ''));
      continue;
    }

    if (mode === 'steps' && (isContinuationLine(line) || (line.length <= 40 && !isHardBoundaryLine(line)))) {
      if (steps.length > 0) {
        steps[steps.length - 1].text = `${steps[steps.length - 1].text} ${line}`;
      }
      continue;
    }

    if (isContinuationLine(line)) {
      if (appendContinuation(tips, line)) continue;
      if (appendContinuation(doshaNotes, line)) continue;
      if (seenPrepMeta && appendContinuation(paragraphs, line)) continue;
    }
  }

  steps.sort((a, b) => a.number - b.number);

  const hasStructure =
    meta.length > 0 ||
    doshaNotes.length > 0 ||
    tips.length > 0 ||
    ingredients.length > 0 ||
    steps.length > 0;

  if (!hasStructure && text.trim()) {
    return {
      meta: [],
      doshaNotes: [],
      tips: [],
      paragraphs: text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean),
      ingredients: [],
      steps: [],
      summary: null,
      isPlainText: true,
    };
  }

  return { meta, doshaNotes, tips, paragraphs, ingredients, steps, summary, isPlainText: false };
}

export function metaLabel(key) {
  const labels = {
    prep: 'Prep',
    cook: 'Cook',
    season: 'Season',
    tastes: 'Tastes',
    servings: 'Servings',
  };
  return labels[key] || key;
}
