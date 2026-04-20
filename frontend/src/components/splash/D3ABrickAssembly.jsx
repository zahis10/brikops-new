import React, { useEffect, useState } from 'react';
import { BrikMark, BlueprintGrid, RadialGlow } from './BrikLogo';
import './splash.css';

function BrickAssembly({ playing = true }) {
  // Final brick grid forming a "B" — 5 cols × 7 rows
  const bw = 18, bh = 10;
  const bricks = [
    // spine (col 0)
    { x: 0, y: 0 }, { x: 0, y: 1 }, { x: 0, y: 2 }, { x: 0, y: 3 },
    { x: 0, y: 4 }, { x: 0, y: 5 }, { x: 0, y: 6 },
    // upper bowl
    { x: 1, y: 0, w: 2 }, { x: 3, y: 0 },
    { x: 3, y: 1 },
    { x: 1, y: 2, w: 2 }, { x: 3, y: 2 },
    // lower bowl
    { x: 1, y: 3, w: 2 }, { x: 3, y: 3 },
    { x: 3, y: 4 },
    { x: 3, y: 5 },
    { x: 1, y: 6, w: 2 }, { x: 3, y: 6 },
  ];

  const gridW = 5 * bw;
  const gridH = 7 * bh;

  return (
    <div style={{
      position: 'relative', width: gridW + 40, height: gridH + 40,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {bricks.map((b, i) => {
        const w = (b.w || 1) * bw - 2;
        const finalX = b.x * bw + 1;
        const finalY = b.y * bh + 1;
        const delay = (b.y * 60 + b.x * 30);
        const isAmber = i === 0 || i === 6;
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

export default function D3ABrickAssembly({ onComplete }) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    // Timing: 1600ms brick-drop animation, then 1500ms HOLD with the
    // assembled "B" static on screen, then 500ms fade-out, then onComplete.
    // Total: 3600ms regardless of data readiness.
    const fadeTimer = setTimeout(() => setFading(true), 3100);
    const completeTimer = setTimeout(() => {
      onComplete && onComplete();
    }, 3600);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <div role="status" aria-live="polite" aria-busy={!fading} aria-label="טוען BrikOps" style={{
      position: 'fixed', inset: 0,
      background: 'linear-gradient(180deg, #3A4258 0%, #323A4E 50%, #2A3142 100%)',
      overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      opacity: fading ? 0 : 1,
      transition: 'opacity 500ms ease-out',
      pointerEvents: fading ? 'none' : 'auto',
      zIndex: 9999,
    }}>
      <BlueprintGrid opacity={0.055} color="#B8C5DB" spacing={36}/>
      <RadialGlow color="#F59E0B" size="45%" opacity={0.1}/>

      <div style={{
        position: 'relative', display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: 24,
      }}>
        <BrickAssembly playing={true}/>
        <div style={{
          fontFamily: '"Rubik", system-ui', fontSize: 22, fontWeight: 600,
          color: '#fff', letterSpacing: -0.3, direction: 'ltr',
        }}>
          Brik<span style={{ color: '#F59E0B' }}>Ops</span>
        </div>
      </div>
    </div>
  );
}
