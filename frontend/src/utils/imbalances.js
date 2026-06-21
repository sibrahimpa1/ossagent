export const DOSHA_IMBALANCE_OPTIONS = {
  Vata: ['Anxiety', 'Poor-Digestion', 'Dry-Skin', 'Insomnia', 'Joint-Pain', 'Constipation'],
  Pitta: ['Inflammation', 'Acid-Reflux', 'Skin-Rashes', 'Anger', 'Excessive-Heat'],
  Kapha: ['Congestion', 'Weight-Gain', 'Lethargy', 'Depression', 'Slow-Digestion', 'Mucus'],
};

export const DOSHA_DOT = { Vata: '#7B6FA0', Pitta: '#C4611A', Kapha: '#4A7C6E' };

export function formatImbalance(label) {
  return label.replace(/-/g, ' ');
}
