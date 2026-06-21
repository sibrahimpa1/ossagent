import './DoshaText.css';

const DOSHA_PATTERN = /(\b(?:Vata|Pitta|Kapha)\b)/gi;

function doshaClass(part) {
  const normalized = part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
  if (normalized === 'Vata') return 'vata';
  if (normalized === 'Pitta') return 'pitta';
  if (normalized === 'Kapha') return 'kapha';
  return null;
}

export default function DoshaText({ text, className = '' }) {
  if (!text) return null;

  const parts = text.split(DOSHA_PATTERN);

  return (
    <span className={className}>
      {parts.map((part, index) => {
        const doshaKey = doshaClass(part);
        if (doshaKey) {
          const label = part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
          return (
            <span key={index} className={`dosha-flag dosha-flag--${doshaKey}`}>
              {label}
            </span>
          );
        }
        return part;
      })}
    </span>
  );
}
