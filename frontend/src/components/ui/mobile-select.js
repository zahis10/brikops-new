import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';

export function MobileSelect({ value, onChange, options, placeholder, className }) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);
  const listRef = useRef(null);

  const selectedLabel = options.find(o => o.value === value)?.label || placeholder || '';

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && listRef.current && value) {
      const selectedEl = listRef.current.querySelector('[data-selected="true"]');
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'center', behavior: 'instant' });
      }
    }
  }, [isOpen, value]);

  const handleSelect = (optionValue) => {
    onChange({ target: { value: optionValue } });
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className={`relative ${className || ''}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-12 w-full items-center justify-between rounded-md border border-input bg-white px-3 py-2 text-base text-right cursor-pointer"
        style={{ fontSize: '16px', touchAction: 'manipulation' }}
      >
        <ChevronDown className={`w-4 h-4 shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        <span className={value ? 'text-slate-900' : 'text-slate-400'}>
          {selectedLabel}
        </span>
      </button>

      {isOpen && (
        <div
          ref={listRef}
          className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-60 overflow-y-auto"
          style={{ zIndex: 9999 }}
        >
          {placeholder && (
            <div
              onClick={() => handleSelect('')}
              className="px-3 py-3 text-right text-slate-400 cursor-pointer hover:bg-slate-50 active:bg-slate-100 border-b border-slate-100"
              style={{ touchAction: 'manipulation' }}
            >
              {placeholder}
            </div>
          )}
          {options.map((option) => (
            <div
              key={option.value}
              data-selected={option.value === value ? 'true' : 'false'}
              onClick={() => handleSelect(option.value)}
              className={`px-3 py-3 text-right cursor-pointer flex items-center justify-between
                ${option.value === value ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-900 hover:bg-slate-50 active:bg-slate-100'}
              `}
              style={{ touchAction: 'manipulation' }}
            >
              {option.value === value && <Check className="w-4 h-4 text-blue-600 shrink-0" />}
              <span>{option.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
