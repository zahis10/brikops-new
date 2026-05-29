import React from 'react';
import { WifiOff } from 'lucide-react';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import { FEATURES } from '../config/features';

const OfflineBanner = () => {
  const online = useOnlineStatus();
  if (!FEATURES.OFFLINE_MODE || online) return null;
  return (
    <div
      dir="rtl"
      className="fixed top-0 inset-x-0 z-[9998] bg-amber-500 text-white text-xs font-medium px-3 py-1.5 flex items-center justify-center gap-2 shadow"
      role="status"
    >
      <WifiOff className="w-3.5 h-3.5" />
      מצב לא מקוון — מוצגים נתונים שנשמרו במכשיר
    </div>
  );
};

export default OfflineBanner;
