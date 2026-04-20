import React from 'react';

export function BrikMark({ size = 120, color = '#fff', accent = '#F59E0B', withAccent = false }) {
  const s = size;
  return (
    <svg width={s} height={s} viewBox="0 0 120 120" fill="none" style={{ display: 'block' }}>
      <rect x="22" y="20" width="16" height="80" rx="2" fill={color}/>
      <path
        d="M38 20 H68 a20 20 0 0 1 20 20 v0 a20 20 0 0 1 -20 20 H38 z"
        fill={color}
      />
      <path
        d="M38 60 H72 a22 22 0 0 1 22 22 v0 a18 18 0 0 1 -18 18 H38 z"
        fill={color}
      />
      {withAccent && <circle cx="38" cy="60" r="3" fill={accent}/>}
    </svg>
  );
}

export function BlueprintGrid({ opacity = 0.06, color = '#fff', spacing = 40 }) {
  return (
    <svg
      style={{
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        opacity, pointerEvents: 'none',
      }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="bp-minor" width={spacing / 4} height={spacing / 4} patternUnits="userSpaceOnUse">
          <path d={`M ${spacing/4} 0 L 0 0 0 ${spacing/4}`} fill="none" stroke={color} strokeWidth="0.5"/>
        </pattern>
        <pattern id="bp-major" width={spacing} height={spacing} patternUnits="userSpaceOnUse">
          <rect width={spacing} height={spacing} fill="url(#bp-minor)"/>
          <path d={`M ${spacing} 0 L 0 0 0 ${spacing}`} fill="none" stroke={color} strokeWidth="1"/>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#bp-major)"/>
    </svg>
  );
}

export function RadialGlow({ color = '#F59E0B', size = '60%', opacity = 0.12 }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: `radial-gradient(circle at center, ${color} 0%, transparent ${size})`,
      opacity,
    }}/>
  );
}
