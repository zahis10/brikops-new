import React from 'react';

// BrikOps logo — matches AppIcon-1024.png
// Bold "B" drawn as a single evenodd path with two rounded-rectangle counters.
export function BrikMark({ size = 120, color = '#F59E0B', bg = null, rounded = true }) {
  const s = size;

  const letter = (
    <svg viewBox="0 0 1024 1024" width="100%" height="100%" style={{ display: 'block' }}>
      <path
        fillRule="evenodd"
        fill={color}
        d="
          M 270 210
          L 610 210
          C 742 210 820 283 820 390
          C 820 463 788 513 735 540
          C 804 567 840 624 840 710
          C 840 822 760 895 620 895
          L 270 895
          Z
          M 400 340
          L 400 475
          L 585 475
          C 640 475 678 450 678 405
          C 678 362 640 340 585 340
          Z
          M 400 565
          L 400 765
          L 605 765
          C 668 765 708 735 708 680
          C 708 620 668 565 605 565
          Z
        "
      />
    </svg>
  );

  if (!bg) {
    return <div style={{ width: s, height: s }}>{letter}</div>;
  }

  return (
    <div style={{
      width: s, height: s,
      background: bg,
      borderRadius: rounded ? s * 0.22 : 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: '0 8px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.08)',
      overflow: 'hidden',
    }}>
      <div style={{ width: '100%', height: '100%' }}>{letter}</div>
    </div>
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
