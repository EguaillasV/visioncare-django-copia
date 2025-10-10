import React from 'react';

export default function MetricBar({ label, value = 0, colorFrom = '#3b82f6', colorTo = '#06b6d4', small = false }) {
  const pct = Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100)));
  return (
    <div className={small ? 'space-y-1' : 'space-y-2'}>
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-700 font-medium truncate" title={label}>{label}</span>
        <span className="text-gray-900 font-semibold tabular-nums">{pct}%</span>
      </div>
      <div className={`w-full ${small ? 'h-2.5' : 'h-3.5'} bg-gray-200 rounded-full overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundImage: `linear-gradient(90deg, ${colorFrom}, ${colorTo})` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
