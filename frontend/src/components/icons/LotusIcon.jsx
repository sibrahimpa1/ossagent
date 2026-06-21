export default function LotusIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Outer petals */}
      <ellipse cx="50" cy="50" rx="8" ry="30" fill={color} opacity="0.3" />
      <ellipse cx="50" cy="50" rx="8" ry="30" fill={color} opacity="0.3" transform="rotate(45 50 50)" />
      <ellipse cx="50" cy="50" rx="8" ry="30" fill={color} opacity="0.3" transform="rotate(90 50 50)" />
      <ellipse cx="50" cy="50" rx="8" ry="30" fill={color} opacity="0.3" transform="rotate(135 50 50)" />

      {/* Middle petals */}
      <ellipse cx="50" cy="50" rx="7" ry="22" fill={color} opacity="0.5" transform="rotate(22.5 50 50)" />
      <ellipse cx="50" cy="50" rx="7" ry="22" fill={color} opacity="0.5" transform="rotate(67.5 50 50)" />
      <ellipse cx="50" cy="50" rx="7" ry="22" fill={color} opacity="0.5" transform="rotate(112.5 50 50)" />
      <ellipse cx="50" cy="50" rx="7" ry="22" fill={color} opacity="0.5" transform="rotate(157.5 50 50)" />

      {/* Center */}
      <circle cx="50" cy="50" r="10" fill={color} />
      <circle cx="50" cy="50" r="6" fill="#F5EFE6" opacity="0.5" />
    </svg>
  );
}
