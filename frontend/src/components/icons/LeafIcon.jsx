export default function LeafIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Leaf shape */}
      <path
        d="M50 10 Q70 30, 75 50 Q70 70, 50 90 Q40 80, 35 70 Q30 50, 35 30 Q40 20, 50 10 Z"
        fill={color}
        opacity="0.8"
      />
      {/* Center vein */}
      <path
        d="M50 15 L50 85"
        stroke="#FFF"
        strokeWidth="1.5"
        opacity="0.4"
      />
      {/* Side veins */}
      {[25, 35, 45, 55, 65, 75].map((y) => (
        <g key={y}>
          <path
            d={`M50 ${y} Q55 ${y + 3}, 60 ${y + 5}`}
            stroke="#FFF"
            strokeWidth="1"
            opacity="0.3"
          />
          <path
            d={`M50 ${y} Q45 ${y + 3}, 40 ${y + 5}`}
            stroke="#FFF"
            strokeWidth="1"
            opacity="0.3"
          />
        </g>
      ))}
    </svg>
  );
}
