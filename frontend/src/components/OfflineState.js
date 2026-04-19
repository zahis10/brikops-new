import React from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';

const OfflineState = ({ onRetry }) => {
  const handleRetry = () => {
    if (typeof onRetry === 'function') {
      onRetry();
    } else if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4" dir="rtl">
      <div className="max-w-sm w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-center">
        <div className="mx-auto w-16 h-16 rounded-full bg-amber-50 flex items-center justify-center mb-4">
          <WifiOff className="w-8 h-8 text-amber-500" />
        </div>
        <h2 className="text-lg font-bold text-slate-800 mb-1" style={{ fontFamily: 'Heebo, sans-serif' }}>
          אין חיבור לאינטרנט
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          בדוק את חיבור הרשת ונסה שוב. הנתונים יטענו ברגע שהחיבור יחזור.
        </p>
        <button
          type="button"
          onClick={handleRetry}
          className="inline-flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-sm font-medium transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          נסה שוב
        </button>
      </div>
    </div>
  );
};

export default OfflineState;
