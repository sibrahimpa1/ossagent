export default function BowlIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Bowl */}
      <path
        d="M20 40 Q20 65, 50 75 Q80 65, 80 40 L20 40"
        fill={color}
        opacity="0.3"
      />
      <ellipse cx="50" cy="40" rx="30" ry="8" fill={color} opacity="0.5" />

      {/* Bowl rim */}
      <ellipse cx="50" cy="40" rx="30" ry="6" stroke={color} strokeWidth="2" fill="none" />

      {/* Steam */}
      <path
        d="M35 30 Q33 25, 35 20"
        stroke={color}
        strokeWidth="2"
        opacity="0.4"
        strokeLinecap="round"
      />
      <path
        d="M50 25 Q48 20, 50 15"
        stroke={color}
        strokeWidth="2"
        opacity="0.4"
        strokeLinecap="round"
      />
      <path
        d="M65 30 Q67 25, 65 20"
        stroke={color}
        strokeWidth="2"
        opacity="0.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
