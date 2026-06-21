import HeartIcon from './HeartIcon';
import './FavoriteButton.css';

export default function FavoriteButton({
  active = false,
  onClick,
  className = '',
  size = 'md',
  title,
  'aria-label': ariaLabel,
}) {
  const sizeClass = size === 'sm' ? 'favorite-btn--sm' : size === 'lg' ? 'favorite-btn--lg' : '';
  const label = ariaLabel || (active ? 'Remove from favorites' : 'Add to favorites');

  return (
    <button
      type="button"
      className={`favorite-btn ${active ? 'favorited' : ''} ${sizeClass} ${className}`.trim()}
      title={title || label}
      aria-label={label}
      onClick={onClick}
    >
      <HeartIcon filled={active} size={size === 'sm' ? 14 : size === 'lg' ? 17 : 15} />
    </button>
  );
}
