import React from 'react';

// Construction scene band under the projects-list header — approved mockup
// 2026-07-17 (visual arc stage 2, "המשך הכניסה"). Pure CSS/SVG, zero logic.
const FADE = 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)';

const ProjectsSceneBand = () => (
  <div
    aria-hidden="true"
    className="relative overflow-hidden pointer-events-none select-none"
    style={{
      height: 118,
      background:
        'radial-gradient(260px 120px at 50% 20%, rgba(245,158,11,.14), transparent 70%), ' +
        'linear-gradient(178deg, #17202b 0%, #212d3b 100%)',
    }}
  >
    <div className="absolute inset-0 mx-auto" style={{ maxWidth: 560, WebkitMaskImage: FADE, maskImage: FADE }}>
      <div
        className="absolute left-0 right-0"
        style={{ bottom: 58, height: 2, background: 'linear-gradient(90deg, transparent, rgba(245,158,11,.5), transparent)', filter: 'blur(1px)' }}
      />
      <svg
        className="absolute bottom-0 left-0 right-0 w-full"
        style={{ height: 96, opacity: 0.55 }}
        viewBox="0 0 340 96"
        preserveAspectRatio="xMidYMax slice"
      >
        <g fill="#111a24">
          <rect x="0" y="44" width="42" height="52" /><rect x="46" y="58" width="30" height="38" />
          <rect x="80" y="36" width="36" height="60" /><rect x="120" y="64" width="26" height="32" />
          <rect x="196" y="50" width="40" height="46" /><rect x="240" y="62" width="28" height="34" />
          <rect x="272" y="40" width="34" height="56" /><rect x="310" y="56" width="30" height="40" />
          <rect x="156" y="10" width="4" height="86" /><rect x="124" y="10" width="96" height="4" />
          <path d="M158 10 L142 26 L158 26 Z" opacity=".9" />
        </g>
        <g fill="#f5a623" opacity=".3">
          <rect x="8" y="52" width="4" height="4" /><rect x="88" y="46" width="4" height="4" />
          <rect x="204" y="58" width="4" height="4" /><rect x="282" y="50" width="4" height="4" />
        </g>
      </svg>
    </div>
  </div>
);

export default ProjectsSceneBand;
