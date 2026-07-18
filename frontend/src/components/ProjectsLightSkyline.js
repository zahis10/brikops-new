import React from 'react';

// Subtle light construction skyline pinned to the viewport bottom — fills the
// empty light area of the projects list (mockup א' art under mockup ב' band).
// Decorative only.
const FADE = 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)';

const ProjectsLightSkyline = () => (
  <div
    aria-hidden="true"
    className="fixed inset-x-0 bottom-0 pointer-events-none select-none"
    style={{ height: 150, zIndex: 0 }}
  >
    <div className="absolute inset-0 mx-auto" style={{ maxWidth: 560, WebkitMaskImage: FADE, maskImage: FADE }}>
      <div
        className="absolute left-0 right-0"
        style={{ bottom: 96, height: 2, background: 'linear-gradient(90deg, transparent, rgba(245,158,11,.28), transparent)', filter: 'blur(1px)' }}
      />
      <svg
        className="absolute bottom-0 left-0 right-0 w-full"
        style={{ height: 150, opacity: 0.75 }}
        viewBox="0 0 340 150"
        preserveAspectRatio="xMidYMax slice"
      >
        <g fill="#d7dfea">
          <rect x="0" y="70" width="42" height="80" /><rect x="46" y="92" width="30" height="58" />
          <rect x="80" y="58" width="36" height="92" /><rect x="120" y="100" width="26" height="50" />
          <rect x="196" y="80" width="40" height="70" /><rect x="240" y="98" width="28" height="52" />
          <rect x="272" y="64" width="34" height="86" /><rect x="310" y="90" width="30" height="60" />
          <rect x="156" y="22" width="4" height="128" /><rect x="124" y="22" width="96" height="4" />
          <path d="M158 22 L142 38 L158 38 Z" opacity=".9" />
        </g>
        <g fill="#f5a623" opacity=".35">
          <rect x="8" y="80" width="4" height="4" /><rect x="88" y="70" width="4" height="4" />
          <rect x="204" y="90" width="4" height="4" /><rect x="282" y="76" width="4" height="4" />
        </g>
      </svg>
    </div>
  </div>
);

export default ProjectsLightSkyline;
