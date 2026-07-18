import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown } from 'lucide-react';

const readMap = (projectId) => {
  try {
    return JSON.parse(localStorage.getItem(`dash_sections_${projectId}`) || '{}');
  } catch {
    return {};
  }
};

export default function DashboardFoldSection({
  id,
  projectId,
  icon: Icon,
  title,
  summary,
  defaultOpen = false,
  forceOpen = 0,
  iconColor = 'text-slate-500',
  count = null,
  children,
}) {
  const [open, setOpen] = useState(() => {
    const m = readMap(projectId);
    return typeof m[id] === 'boolean' ? m[id] : defaultOpen;
  });
  const firstForce = useRef(true);
  const firstKey = useRef(true);

  useEffect(() => {
    if (firstKey.current) {
      firstKey.current = false;
      return;
    }
    const m = readMap(projectId);
    setOpen(typeof m[id] === 'boolean' ? m[id] : defaultOpen);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, id]);

  useEffect(() => {
    if (firstForce.current) {
      firstForce.current = false;
      return;
    }
    if (forceOpen > 0) setOpen(true);
  }, [forceOpen]);

  const toggle = () => {
    setOpen(prev => {
      const next = !prev;
      try {
        const m = readMap(projectId);
        m[id] = next;
        localStorage.setItem(`dash_sections_${projectId}`, JSON.stringify(m));
      } catch {
        /* localStorage unavailable — state stays in memory */
      }
      return next;
    });
  };

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-2 p-3.5 text-right hover:bg-slate-50 transition-colors"
        aria-expanded={open}
      >
        {Icon && <Icon className={`w-4 h-4 shrink-0 ${iconColor}`} />}
        <span className="text-sm font-bold text-slate-700 shrink-0">{title}</span>
        {count > 0 && (
          <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full shrink-0">{count}</span>
        )}
        {summary && <span className="text-xs text-slate-400 truncate flex-1 text-right">{summary}</span>}
        {!summary && <span className="flex-1" />}
        <ChevronDown className={`w-4 h-4 text-slate-300 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
