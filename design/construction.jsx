// ─────────────────────────────────────────────────────────────
// D3 — CONSTRUCTION-THEMED ANIMATIONS
// Three concepts, timed 1.5-2s, all in brand palette.
// ─────────────────────────────────────────────────────────────

// ============ OPTION A — BRICK ASSEMBLY ============
// 12 bricks fall from top, snap into the shape of "B"
function BrickAssembly({ playing = true, onComplete }) {
  // Final brick grid forming a "B" — 5 cols × 7 rows, filled cells = B shape
  // x,y in grid units; brickW/H in px
  const bw = 18, bh = 10;
  const bricks = [
    // spine (col 0)
    { x: 0, y: 0 }, { x: 0, y: 1 }, { x: 0, y: 2 }, { x: 0, y: 3 },
    { x: 0, y: 4 }, { x: 0, y: 5 }, { x: 0, y: 6 },
    // upper bowl top/bottom (wide brick = 2 units)
    { x: 1, y: 0, w: 2 }, { x: 3, y: 0 },
    { x: 3, y: 1 }, // right side upper
    { x: 1, y: 2, w: 2 }, { x: 3, y: 2 }, // middle divide
    // lower bowl
    { x: 1, y: 3, w: 2 }, { x: 3, y: 3 },
    { x: 3, y: 4 },
    { x: 3, y: 5 },
    { x: 1, y: 6, w: 2 }, { x: 3, y: 6 },
  ];

  const gridW = 5 * bw;
  const gridH = 7 * bh;
  const totalDur = 1600; // ms

  return (
    <div style={{
      position: 'relative', width: gridW + 40, height: gridH + 40,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {bricks.map((b, i) => {
        const w = (b.w || 1) * bw - 2;
        const finalX = b.x * bw + 1;
        const finalY = b.y * bh + 1;
        // stagger drop by column first, then row
        const delay = (b.y * 60 + b.x * 30);
        const isAmber = i === 0 || i === 6; // couple of amber bricks for brand pop
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              top: 20 + finalY, left: 20 + finalX,
              width: w, height: bh - 2,
              background: isAmber ? '#F59E0B' : '#fff',
              borderRadius: 1.5,
              boxShadow: isAmber
                ? '0 2px 8px rgba(245,158,11,0.4)'
                : '0 1px 2px rgba(0,0,0,0.2)',
              animation: playing
                ? `brickDrop 620ms cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}ms both`
                : 'none',
              opacity: playing ? undefined : 1,
            }}
          />
        );
      })}
    </div>
  );
}

// ============ OPTION B — BLUEPRINT TO BUILDING ============
// SVG path draws the B outline (CAD feel), then fills solid
function BlueprintToBuilding({ playing = true }) {
  // Simplified B outline path
  const bPath = "M 20 10 L 20 90 L 60 90 Q 82 90 82 72 Q 82 56 68 52 Q 80 48 80 34 Q 80 10 60 10 Z M 32 22 L 56 22 Q 68 22 68 32 Q 68 44 56 44 L 32 44 Z M 32 56 L 58 56 Q 72 56 72 68 Q 72 78 58 78 L 32 78 Z";

  return (
    <div style={{ position: 'relative', width: 220, height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width="180" height="180" viewBox="0 0 100 100" style={{ overflow: 'visible' }}>
        {/* construction dimension lines (technical aesthetic) */}
        <g style={{
          animation: playing ? 'bpFadeOut 600ms ease 900ms forwards' : 'none',
          opacity: playing ? 1 : 0,
        }}>
          <line x1="5" y1="10" x2="5" y2="90" stroke="#F59E0B" strokeWidth="0.4" strokeDasharray="2 1.5"/>
          <line x1="2" y1="10" x2="8" y2="10" stroke="#F59E0B" strokeWidth="0.4"/>
          <line x1="2" y1="90" x2="8" y2="90" stroke="#F59E0B" strokeWidth="0.4"/>
          <text x="1" y="53" fontSize="3" fill="#F59E0B" fontFamily="monospace">80</text>

          <line x1="20" y1="96" x2="82" y2="96" stroke="#F59E0B" strokeWidth="0.4" strokeDasharray="2 1.5"/>
          <line x1="20" y1="93" x2="20" y2="99" stroke="#F59E0B" strokeWidth="0.4"/>
          <line x1="82" y1="93" x2="82" y2="99" stroke="#F59E0B" strokeWidth="0.4"/>
          <text x="48" y="100" fontSize="3" fill="#F59E0B" fontFamily="monospace">62</text>

          {/* construction crosshairs */}
          <g stroke="#F59E0B" strokeWidth="0.3" opacity="0.6">
            <line x1="85" y1="8" x2="92" y2="8"/><line x1="88" y1="5" x2="88" y2="11"/>
            <line x1="85" y1="92" x2="92" y2="92"/><line x1="88" y1="89" x2="88" y2="95"/>
          </g>
        </g>

        {/* B path — stroke draws first, then fills */}
        <path
          d={bPath}
          fill="#fff"
          stroke="#fff"
          strokeWidth="0.8"
          fillRule="evenodd"
          style={{
            strokeDasharray: 400,
            strokeDashoffset: playing ? 400 : 0,
            fillOpacity: playing ? 0 : 1,
            animation: playing
              ? 'bpDraw 900ms ease-out forwards, bpFill 500ms ease 900ms forwards'
              : 'none',
          }}
        />

        {/* amber fill-in accent — a spark along the bottom when complete */}
        <rect
          x="20" y="88" width="62" height="3"
          fill="#F59E0B"
          style={{
            opacity: 0,
            animation: playing ? 'bpAccent 400ms ease 1300ms forwards' : 'none',
          }}
        />
      </svg>
    </div>
  );
}

// ============ OPTION C — TOOLS ASSEMBLING ============
// Hammer, level, trowel icons fly in, form a B, then fade to clean B
function ToolsAssembling({ playing = true }) {
  return (
    <div style={{ position: 'relative', width: 220, height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Tools fly in from 3 corners */}
      <Tool kind="hammer" from={{ x: -120, y: -80, r: -45 }} to={{ x: -40, y: -30, r: 0 }} delay={0} playing={playing}/>
      <Tool kind="level"  from={{ x: 120, y: -100, r: 30 }} to={{ x: 30, y: -40, r: 0 }} delay={120} playing={playing}/>
      <Tool kind="trowel" from={{ x: 100, y: 120, r: -30 }} to={{ x: 20, y: 40, r: 0 }} delay={240} playing={playing}/>

      {/* Tools fade out, clean B emerges */}
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: 0,
        animation: playing ? 'toolsBIn 500ms ease 1100ms forwards' : 'none',
      }}>
        <BrikMark size={140} color="#fff" accent="#F59E0B" withAccent/>
      </div>
    </div>
  );
}

function Tool({ kind, from, to, delay, playing }) {
  const style = {
    position: 'absolute',
    top: '50%', left: '50%',
    transform: `translate(calc(-50% + ${from.x}px), calc(-50% + ${from.y}px)) rotate(${from.r}deg) scale(0.7)`,
    opacity: 0,
    '--tx-to': `${to.x}px`, '--ty-to': `${to.y}px`, '--r-to': `${to.r}deg`,
    '--tx-from': `${from.x}px`, '--ty-from': `${from.y}px`, '--r-from': `${from.r}deg`,
    animation: playing ? `toolFly 900ms cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms forwards, toolFade 300ms ease 1100ms forwards` : 'none',
  };

  if (kind === 'hammer') {
    return (
      <svg width="50" height="50" viewBox="0 0 50 50" style={style}>
        <rect x="22" y="22" width="6" height="26" rx="1" fill="#fff"/>
        <path d="M10 10 L34 10 L38 18 L34 24 L10 24 Z" fill="#F59E0B"/>
      </svg>
    );
  }
  if (kind === 'level') {
    return (
      <svg width="60" height="30" viewBox="0 0 60 30" style={style}>
        <rect x="2" y="8" width="56" height="14" rx="2" fill="#fff"/>
        <rect x="26" y="11" width="8" height="8" rx="1" fill="#F59E0B"/>
        <circle cx="30" cy="15" r="1.5" fill="#323A4E"/>
      </svg>
    );
  }
  // trowel
  return (
    <svg width="40" height="50" viewBox="0 0 40 50" style={style}>
      <path d="M5 5 L35 5 L30 25 L10 25 Z" fill="#fff"/>
      <rect x="17" y="25" width="6" height="20" rx="1" fill="#F59E0B"/>
    </svg>
  );
}

Object.assign(window, { BrickAssembly, BlueprintToBuilding, ToolsAssembling, Tool });
