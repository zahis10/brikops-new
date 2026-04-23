import React from 'react';

/**
 * 0-100 donut gauge. RTL-safe (no direction-specific markup).
 * @param {number} score       0..100
 * @param {number} size        px, default 180
 * @param {number} stroke      px, default 14
 * @param {string} label       optional Hebrew label under the number
 */
export default function SafetyScoreGauge({ score = 0, size = 180, stroke = 14, label }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const offset = circumference * (1 - clamped / 100);

  let color = '#ef4444';
  let tierHe = 'דורש תיקון';
  if (clamped >= 85) { color = '#10b981'; tierHe = 'מצוין'; }
  else if (clamped >= 70) { color = '#3b82f6'; tierHe = 'טוב'; }
  else if (clamped >= 50) { color = '#f59e0b'; tierHe = 'תקין'; }

  return (
    <div className="flex flex-col items-center justify-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-label={`ציון בטיחות ${clamped} מתוך 100`}
        role="img"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#e5e7eb"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 400ms ease-out, stroke 400ms ease-out' }}
        />
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.28}
          fontWeight="800"
          fill="#0f172a"
        >
          {clamped}
        </text>
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.08}
          fontWeight="600"
          fill="#64748b"
        >
          {tierHe}
        </text>
      </svg>
      {label && <p className="text-sm text-slate-600 mt-2 font-medium">{label}</p>}
    </div>
  );
}
