import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function PaymentFailurePage() {
  const navigate = useNavigate();

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', fontFamily: 'sans-serif', direction: 'rtl', textAlign: 'center',
      background: '#fef2f2', padding: '2rem',
    }}>
      <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>❌</div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#991b1b', marginBottom: '0.5rem' }}>
        התשלום נכשל
      </h1>
      <p style={{ fontSize: '1rem', color: '#4b5563', marginBottom: '1.5rem' }}>
        אנא נסה שנית או פנה לתמיכה
      </p>
      <button
        onClick={() => navigate(-1)}
        style={{
          background: '#374151', color: '#fff', border: 'none', borderRadius: '0.5rem',
          padding: '0.75rem 2rem', fontSize: '1rem', fontWeight: 600, cursor: 'pointer',
        }}
      >
        חזור
      </button>
    </div>
  );
}
