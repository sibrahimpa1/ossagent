import { useState, useEffect } from 'react';
import './LoadingSpinner.css';

const LOADING_MESSAGES = [
  'Consulting the knowledge graph...',
  'Traversing dosha relationships...',
  'Finding your perfect balance...',
  'Asking the ancient texts...',
  'Mixing spices with intention...',
  'Balancing the five elements...',
];

export const GENERATION_MESSAGES = [
  'Generating fresh recipes...',
  ...LOADING_MESSAGES,
];

export default function LoadingSpinner({
  message,
  messages = LOADING_MESSAGES,
  variant = 'full',
}) {
  const [textIndex, setTextIndex] = useState(0);
  const displayMessages = message ? [message] : messages;

  useEffect(() => {
    setTextIndex(0);
  }, [message, messages]);

  useEffect(() => {
    if (displayMessages.length <= 1) return undefined;
    const interval = setInterval(() => {
      setTextIndex((i) => (i + 1) % displayMessages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [displayMessages.length]);

  return (
    <div className={`loading-screen ${variant === 'overlay' ? 'loading-screen--overlay' : ''}`.trim()}>
      <div className="loading-mandala-wrap">
        <div className="loading-glow" />
        <svg viewBox="-68 -68 136 136" width="150" height="150" className="loading-mandala">
          <g className="loading-mandala-spin">
            <g fill="rgba(28,51,40,0.12)" stroke="rgba(28,51,40,0.3)" strokeWidth="1">
              {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
                <ellipse key={deg} cx="0" cy="-32" rx="11" ry="30" transform={`rotate(${deg})`} />
              ))}
            </g>
            <g fill="rgba(28,51,40,0.26)" stroke="rgba(28,51,40,0.45)" strokeWidth="1">
              {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((deg) => (
                <ellipse key={deg} cx="0" cy="-20" rx="9" ry="20" transform={`rotate(${deg})`} />
              ))}
            </g>
            <circle cx="0" cy="0" r="9" fill="#C4611A" />
          </g>
        </svg>
      </div>

      <div className="loading-text-wrap">
        <div className="loading-text">{displayMessages[textIndex]}</div>
      </div>

      <div className="loading-dots">
        {[0, 1, 2].map((i) => (
          <span key={i} className="loading-dot" style={{ animationDelay: `${i * 0.3}s` }} />
        ))}
      </div>
    </div>
  );
}
