import './BackButton.css';

export default function BackButton({ onClick, label, className = '' }) {
  return (
    <button
      type="button"
      className={`back-button ${className}`.trim()}
      onClick={onClick}
      aria-label={label || 'Go back'}
    >
      ←
    </button>
  );
}
