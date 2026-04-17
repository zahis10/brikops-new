import React from 'react';

const CategoryPill = ({ children, className = '' }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[11px] font-medium whitespace-nowrap ${className}`}>
    {children}
  </span>
);

export default CategoryPill;
