import React from 'react';

// Simple circular gauge using SVG to visualize a 0..1 value as percentage
export default function Gauge({
  label = 'Valor',
  value = 0,
  size = 140,
  strokeWidth = 12,
  color = '#0ea5e9',
  trackColor = '#e5e7eb',
  textColor = '#111827'
}) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  const pct = Math.round(v * 100);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - v);

  return (
    <div className="flex flex-col items-center justify-center select-none">
      <svg width={size} height={size} className="block">
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth={strokeWidth}
          />
          {/* Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 400ms ease' }}
          />
        </g>
        {/* Center text */}
        <text
          x="50%"
          y="50%"
          dominantBaseline="middle"
          textAnchor="middle"
          style={{ fontSize: size * 0.22, fontWeight: 700, fill: textColor }}
        >
          {pct}%
        </text>
      </svg>
      {label && (
        <div className="mt-2 text-sm font-medium text-gray-700 text-center" title={label}>
          {label}
        </div>
      )}
    </div>
  );
}
