import { tendencyLabel } from '../utils/doshas';
import './DoshaPill.css';

const DOSHA_STYLES = {
  Vata: { bg: 'var(--dosha-vata)', soft: 'var(--dosha-vata-soft)', text: 'var(--dosha-vata-text)' },
  Pitta: { bg: 'var(--dosha-pitta)', soft: 'var(--dosha-pitta-soft)', text: 'var(--dosha-pitta)' },
  Kapha: { bg: 'var(--dosha-kapha)', soft: 'var(--dosha-kapha-soft)', text: 'var(--dosha-kapha-text)' },
};

export default function DoshaPill({ dosha, variant = 'filled', size = 'md', tendency = null }) {
  const style = DOSHA_STYLES[dosha] || { bg: 'var(--text-muted)', soft: 'var(--bg-muted)', text: 'var(--text-secondary)' };
  const tendencyText = tendencyLabel(tendency, { short: true });

  return (
    <span
      className={`dosha-pill dosha-pill--${variant} dosha-pill--${size}${tendencyText ? ' dosha-pill--has-tendency' : ''}`}
      style={{
        '--dosha-bg': style.bg,
        '--dosha-soft': style.soft,
        '--dosha-text': style.text,
      }}
    >
      <span className="dosha-pill-name">{dosha}</span>
      {tendencyText && (
        <span className={`dosha-pill-tendency dosha-pill-tendency--${tendency}`}>
          {tendencyText}
        </span>
      )}
    </span>
  );
}

export function FitBadge({ fit, size = 'md' }) {
  const fitKey = (fit || 'Works').toLowerCase();
  return <span className={`fit-badge fit-badge--${fitKey} fit-badge--${size}`}>{fit}</span>;
}
