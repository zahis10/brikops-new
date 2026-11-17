import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

// #622 — one tab bar for page-level tabs: text tabs, the active one in navy with an orange underline.
// fit: true = equal widths, false = natural widths with horizontal scroll, 'auto' = equal widths for up to 4 tabs.
// When the tabs scroll, a 44px arrow appears on the side that has more tabs (so hidden tabs are never a surprise).
const ARROW_CLASS = 'absolute top-0 bottom-0 w-11 flex items-center justify-center bg-white text-slate-500 hover:text-slate-700 border-slate-200';

const TabBar = ({ tabs = [], activeId, onSelect, fit = 'auto', maxWidth = '', className = '', ariaLabel }) => {
  const equal = fit === 'auto' ? tabs.length <= 4 : !!fit;
  const listRef = useRef(null);
  const [more, setMore] = useState({ start: false, end: false });

  const update = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    const pos = Math.abs(el.scrollLeft); // RTL: 0 at the start (right side), grows towards the end (left side)
    setMore({ start: pos > 4, end: pos < max - 4 });
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (!el || equal) return undefined;
    update();
    el.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      el.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, [equal, update, tabs.length]);

  const scrollByTabs = (dir) => {
    const el = listRef.current;
    if (el) el.scrollBy({ left: dir * Math.round(el.clientWidth * 0.8), behavior: 'smooth' });
  };

  return (
    <div className={`bg-white border-b border-slate-200 ${className}`} dir="rtl">
      <div className={`relative mx-auto ${maxWidth}`}>
        <div
          ref={listRef}
          role="tablist"
          aria-label={ariaLabel}
          className={`flex ${equal ? '' : 'overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden'}`}
        >
          {tabs.map((tab) => {
            const active = tab.id === activeId;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onSelect(tab.id)}
                className={`${equal ? 'flex-1 min-w-0 px-1' : 'flex-shrink-0 px-4'} min-h-[48px] text-sm font-semibold whitespace-nowrap border-b-[3px] transition-colors touch-manipulation ${
                  active ? 'text-navy border-amber-500' : 'text-slate-500 border-transparent hover:text-slate-700'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        {!equal && more.start && (
          <button type="button" aria-label="לטאבים הקודמים" onClick={() => scrollByTabs(1)} className={`${ARROW_CLASS} right-0 border-l`}>
            <ChevronRight className="w-5 h-5" />
          </button>
        )}
        {!equal && more.end && (
          <button type="button" aria-label="לטאבים נוספים" onClick={() => scrollByTabs(-1)} className={`${ARROW_CLASS} left-0 border-r`}>
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}
      </div>
    </div>
  );
};

export default TabBar;
