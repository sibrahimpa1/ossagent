export default function SpiceIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Ginger root shape */}
      <path
        d="M40 30 Q35 35, 30 45 Q28 55, 35 60 Q45 63, 50 58 Q55 53, 60 48 Q65 43, 70 45 Q75 48, 75 55 Q73 65, 65 70 Q55 72, 45 68 Q35 65, 28 58 Q20 50, 25 40 Q30 32, 40 30 Z"
        fill={color}
        opacity="0.7"
      />
      {/* Details/texture */}
      <circle cx="42" cy="42" r="3" fill={color} opacity="0.5" />
      <circle cx="55" cy="50" r="2.5" fill={color} opacity="0.5" />
      <circle cx="48" cy="55" r="2" fill={color} opacity="0.5" />
      <circle cx="38" cy="52" r="2" fill={color} opacity="0.5" />
    </svg>
  );
}
