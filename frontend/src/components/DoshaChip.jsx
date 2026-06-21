import './DoshaChip.css';

const DOSHA_COLORS = {
  Vata: 'var(--dosha-vata)',
  Pitta: 'var(--dosha-pitta)',
  Kapha: 'var(--dosha-kapha)',
};

export default function DoshaChip({ dosha, isPrimary = false, small = false }) {
  const color = DOSHA_COLORS[dosha] || 'var(--text-gray)';

  return (
    <span
      className={`dosha-chip ${isPrimary ? 'primary' : 'secondary'} ${small ? 'small' : ''}`}
      style={{ '--dosha-color': color }}
    >
      {dosha}
      {isPrimary && ' ★'}
    </span>
  );
}
