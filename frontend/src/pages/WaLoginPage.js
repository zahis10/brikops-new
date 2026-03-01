import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const API = process.env.REACT_APP_API_URL || '';

export default function WaLoginPage() {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const existing = localStorage.getItem('token');
    if (existing && !window.location.hash && !searchParams.get('token')) {
      navigate('/', { replace: true });
      return;
    }

    const hash = window.location.hash;
    if (hash && hash.startsWith('#token=')) {
      const jwt = hash.substring(7);
      localStorage.setItem('token', jwt);
      window.history.replaceState({}, document.title, '/');
      window.location.href = '/';
      return;
    }

    const waToken = searchParams.get('token');
    if (waToken) {
      window.location.href = `${API}/api/auth/wa/verify?token=${encodeURIComponent(waToken)}`;
      return;
    }

    setError('קישור לא תקין');
  }, [searchParams, navigate]);

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', direction: 'rtl' }}>
        <div style={{ textAlign: 'center' }}>
          <h2>{error}</h2>
          <a href="/login" style={{ color: '#2563eb' }}>חזרה לדף ההתחברות</a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', direction: 'rtl' }}>
      <p>מתחבר...</p>
    </div>
  );
}
