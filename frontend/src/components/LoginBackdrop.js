import React from 'react';

// Decorative backdrop for the auth screens (login / onboarding / password) —
// approved mockup 2026-07-17 ("קו רקיע" + "הוו המנוף").
// Pure CSS/SVG, zero logic, zero interaction.
const FADE = 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)';

const LoginBackdrop = () => (
  <div
    aria-hidden="true"
    className="absolute inset-0 overflow-hidden pointer-events-none select-none"
    style={{
      background:
        'radial-gradient(420px 280px at 50% 26%, rgba(245,158,11,.17), transparent 65%), ' +
        'linear-gradient(178deg, #17202b 0%, #1f2a37 60%, #26303c 100%)',
    }}
  >
    <div
      className="absolute inset-0 mx-auto"
      style={{ maxWidth: 560, WebkitMaskImage: FADE, maskImage: FADE }}
    >
      {/* crane jib entering from the top, cable + hook "holding" the card */}
      <svg
        className="absolute top-0 left-0 right-0 w-full"
        style={{ height: 150, opacity: 0.85 }}
        viewBox="0 0 340 150"
        preserveAspectRatio="xMidYMin slice"
      >
        <g fill="#3e5065">
          <rect x="128" y="20" width="220" height="5" />
          <rect x="150" y="36" width="198" height="3.5" />
          <rect x="178" y="39" width="15" height="6" rx="1" />
          <rect x="185" y="45" width="1.7" height="33" />
          <rect x="181" y="78" width="10" height="6" rx="1" />
        </g>
        <g stroke="#3e5065" strokeWidth="2.4" fill="none">
          <path d="M340 36 L322 25 L304 36 L286 25 L268 36 L250 25 L232 36 L214 25 L196 36 L178 25 L160 36 L151 31" />
          <path d="M129 24 L151 37" />
        </g>
        <path d="M186 84 v4 a5.2 5.2 0 1 1 -9.5 -1.8" stroke="#3e5065" strokeWidth="2.6" fill="none" strokeLinecap="round" />
        <circle cx="128" cy="22" r="7.5" fill="#f5a623" opacity=".15" />
        <circle cx="128" cy="22" r="3" fill="#f5a623" opacity=".9" />
        <g stroke="#64788e" strokeWidth="1.6" fill="none" opacity=".45" strokeLinecap="round">
          <path d="M52 48 q4.5 -4.5 9 0 q4.5 -4.5 9 0" />
          <path d="M84 33 q3.5 -3.5 7 0 q3.5 -3.5 7 0" />
        </g>
      </svg>

      {/* glowing orange horizon line */}
      <div
        className="absolute left-0 right-0"
        style={{
          bottom: 118,
          height: 2,
          background: 'linear-gradient(90deg, transparent, rgba(245,158,11,.55), transparent)',
          filter: 'blur(1px)',
        }}
      />

      {/* buildings + cranes skyline */}
      <svg
        className="absolute bottom-0 left-0 right-0 w-full"
        style={{ height: 190, opacity: 0.55 }}
        viewBox="0 0 340 190"
        preserveAspectRatio="xMidYMax slice"
      >
        <g fill="#111a24">
          <rect x="0" y="95" width="42" height="95" />
          <rect x="46" y="120" width="30" height="70" />
          <rect x="80" y="80" width="36" height="110" />
          <rect x="120" y="130" width="26" height="60" />
          <rect x="196" y="105" width="40" height="85" />
          <rect x="240" y="128" width="28" height="62" />
          <rect x="272" y="88" width="34" height="102" />
          <rect x="310" y="118" width="30" height="72" />
          <rect x="156" y="38" width="5" height="152" />
          <rect x="118" y="38" width="112" height="5" />
          <rect x="118" y="43" width="3" height="16" />
          <path d="M158 38 L138 58 L158 58 Z" opacity=".9" />
          <rect x="216" y="43" width="2" height="26" />
          <rect x="211" y="69" width="12" height="9" />
          <g opacity=".55">
            <rect x="292" y="62" width="4" height="60" />
            <rect x="266" y="62" width="58" height="4" />
            <rect x="316" y="66" width="2" height="18" />
          </g>
        </g>
        <g fill="#f5a623" opacity=".28">
          <rect x="8" y="105" width="4" height="4" /><rect x="20" y="118" width="4" height="4" />
          <rect x="88" y="92" width="4" height="4" /><rect x="100" y="108" width="4" height="4" />
          <rect x="204" y="115" width="4" height="4" /><rect x="282" y="100" width="4" height="4" />
          <rect x="296" y="128" width="4" height="4" /><rect x="318" y="128" width="4" height="4" />
        </g>
      </svg>
    </div>
  </div>
);

export default LoginBackdrop;
