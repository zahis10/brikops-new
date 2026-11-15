import React from 'react';

const Breadcrumbs = ({ items = [], separator = '›', className = '' }) => {
  const parts = items.filter(Boolean);
  if (parts.length === 0) return null;
  const last = parts.length - 1;
  return (
    <div className={`flex items-center gap-1.5 text-xs min-w-0 overflow-hidden ${className}`}>
      {parts.map((item, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span aria-hidden="true" className="flex-shrink-0">{separator}</span>}
          <span
            className={i === last && last > 0 ? 'flex-shrink-0 whitespace-nowrap' : 'truncate'}
            style={i === 0 && last > 0 ? { flexShrink: 100000, minWidth: '3ch' } : undefined}
          >
            {item}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
};

export default Breadcrumbs;
