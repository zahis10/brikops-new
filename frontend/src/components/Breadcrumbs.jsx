import React from 'react';

const Breadcrumbs = ({ items = [], separator = '›', className = '' }) => {
  const parts = items.filter(Boolean);
  if (parts.length === 0) return null;
  return (
    <div className={`flex items-center gap-1.5 text-xs ${className}`}>
      {parts.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span aria-hidden="true">{separator}</span>}
          <span className="truncate">{item}</span>
        </React.Fragment>
      ))}
    </div>
  );
};

export default Breadcrumbs;
