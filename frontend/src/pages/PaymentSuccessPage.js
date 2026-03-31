import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function PaymentSuccessPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => navigate('/projects', { replace: true }), 3000);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', fontFamily: 'sans-serif', direction: 'rtl', textAlign: 'center',
      background: '#f0fdf4', padding: '2rem',
    }}>
      <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>✅</div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#166534', marginBottom: '0.5rem' }}>
        התשלום התקבל בהצלחה!
      </h1>
      <p style={{ fontSize: '1rem', color: '#4b5563' }}>
        מעבירים אותך חזרה למערכת…
      </p>
    </div>
  );
}
