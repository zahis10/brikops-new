import React, { useState, useEffect } from 'react';
import { BrikMark, BlueprintGrid, RadialGlow } from './BrikLogo';
import './splash.css';

function Shimmer({ children, style = {} }) {
  return (
    <div style={{
      position: 'relative', overflow: 'hidden',
      background: 'rgba(255,255,255,0.06)',
      border: '1px solid rgba(255,255,255,0.04)',
      ...style,
    }}>
      {children}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.08) 45%, rgba(245,158,11,0.06) 50%, rgba(255,255,255,0.08) 55%, transparent 100%)',
        animation: 'shimmerRTL 1.8s ease-in-out infinite',
      }}/>
    </div>
  );
}

function SkeletonHeader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <Shimmer style={{ width: 140, height: 20, borderRadius: 6 }}/>
      <Shimmer style={{ width: 36, height: 36, borderRadius: 10 }}/>
    </div>
  );
}

function SkeletonKPIs() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
      {[0,1,2].map(i => (
        <Shimmer key={i} style={{ height: 64, borderRadius: 12 }}/>
      ))}
    </div>
  );
}

function SkeletonCard() {
  return (
    <Shimmer style={{ height: 82, borderRadius: 14, padding: 14 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(255,255,255,0.04)' }}/>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ width: '60%', height: 10, borderRadius: 4, background: 'rgba(255,255,255,0.05)' }}/>
          <div style={{ width: '40%', height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.04)' }}/>
        </div>
        <div style={{ width: 40, height: 20, borderRadius: 10, background: 'rgba(245,158,11,0.12)' }}/>
      </div>
    </Shimmer>
  );
}

export default function D2DailySplash({ isReady = false, loadingText = 'מתחבר' }) {
  // phase 0: logo only (first 300ms, matches native splash)
  // phase 1: skeleton appears, shimmer runs
  // phase 2: fading out (when isReady=true)
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setPhase(p => (p < 1 ? 1 : p)), 300);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (isReady) setPhase(2);
  }, [isReady]);

  return (
    <div role="status" aria-live="polite" aria-busy={phase !== 2} aria-label={loadingText} style={{
      position: 'fixed', inset: 0,
      background: 'linear-gradient(180deg, #3A4258 0%, #323A4E 50%, #2A3142 100%)',
      overflow: 'hidden',
      direction: 'rtl',
      opacity: phase === 2 ? 0 : 1,
      transition: 'opacity 500ms ease-out',
      pointerEvents: phase === 2 ? 'none' : 'auto',
      zIndex: 9998,
    }}>
      <BlueprintGrid opacity={0.055} color="#B8C5DB" spacing={36}/>
      <RadialGlow color="#F59E0B" size="45%" opacity={0.1}/>

      {/* LOGO — breathing pulse */}
      <div style={{
        position: 'absolute',
        top: '22%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
      }}>
        <div style={{
          animation: 'brikBreathe 2.4s ease-in-out infinite',
          filter: 'drop-shadow(0 0 24px rgba(245, 158, 11, 0.25))',
        }}>
          <BrikMark size={88} color="#F59E0B" accent="#fff" withAccent/>
        </div>
        <div style={{
          fontFamily: '"Rubik", system-ui', fontSize: 18, fontWeight: 600,
          color: '#fff', letterSpacing: -0.2, direction: 'ltr',
        }}>
          Brik<span style={{ color: '#F59E0B' }}>Ops</span>
        </div>
        <div style={{
          fontFamily: '"Rubik", system-ui', fontSize: 13, fontWeight: 400,
          color: 'rgba(255,255,255,0.45)', letterSpacing: 0.2,
          minHeight: 16, marginTop: 4,
        }}>
          {loadingText}{loadingText && '...'}
        </div>
      </div>

      {/* SKELETON — appears in phase 1 */}
      <div style={{
        position: 'absolute',
        top: '48%', right: 0, left: 0, bottom: 0,
        padding: '0 20px',
        display: 'flex', flexDirection: 'column', gap: 14,
        opacity: phase >= 1 ? 1 : 0,
        transform: phase >= 1 ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 300ms ease, transform 300ms cubic-bezier(0.22, 1, 0.36, 1)',
      }}>
        <SkeletonHeader/>
        <SkeletonKPIs/>
        <SkeletonCard/>
        <SkeletonCard/>
      </div>
    </div>
  );
}
