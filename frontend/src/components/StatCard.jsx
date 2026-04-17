import React from 'react';

const StatCard = ({ label, value }) => (
  <div className="px-3 text-center" dir="rtl">
    <div className="text-3xl font-bold text-slate-900 tabular-nums leading-none">
      {value ?? 0}
    </div>
    <div className="text-xs text-slate-500 mt-1.5 font-medium">{label}</div>
  </div>
);

export default StatCard;
