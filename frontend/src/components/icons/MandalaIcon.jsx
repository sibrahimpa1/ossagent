export default function MandalaIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Outer ring */}
      <circle cx="50" cy="50" r="40" stroke={color} strokeWidth="1" opacity="0.3" />
      <circle cx="50" cy="50" r="35" stroke={color} strokeWidth="1" opacity="0.4" />

      {/* Petals around */}
      {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((angle) => (
        <ellipse
          key={angle}
          cx="50"
          cy="50"
          rx="3"
          ry="15"
          fill={color}
          opacity="0.4"
          transform={`rotate(${angle} 50 50)`}
        />
      ))}

      {/* Middle circle */}
      <circle cx="50" cy="50" r="20" stroke={color} strokeWidth="1.5" opacity="0.5" />

      {/* Inner details */}
      {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
        <line
          key={angle}
          x1="50"
          y1="50"
          x2={50 + 15 * Math.cos((angle * Math.PI) / 180)}
          y2={50 + 15 * Math.sin((angle * Math.PI) / 180)}
          stroke={color}
          strokeWidth="1"
          opacity="0.6"
        />
      ))}

      {/* Center */}
      <circle cx="50" cy="50" r="8" fill={color} opacity="0.7" />
      <circle cx="50" cy="50" r="4" fill={color} opacity="0.9" />
    </svg>
  );
}
