export default function OmIcon({ size = 24, color = "currentColor", className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Om symbol - simplified artistic representation */}
      <path
        d="M30 45 Q25 35, 35 30 Q45 25, 50 35 Q55 45, 50 55 Q45 65, 35 60 Q25 55, 30 45"
        fill={color}
        opacity="0.8"
      />
      <circle cx="70" cy="35" r="8" fill={color} opacity="0.8" />
      <path
        d="M50 55 Q60 50, 70 55 L70 75 Q60 80, 50 75 Z"
        fill={color}
        opacity="0.8"
      />
      <path
        d="M20 70 Q30 65, 40 70 Q45 75, 40 80 Q30 85, 20 80 Z"
        fill={color}
        opacity="0.6"
      />
      <circle cx="50" cy="20" r="3" fill={color} />
    </svg>
  );
}
