import React, { useState } from 'react';
import { X, ChevronDown, Loader2, RefreshCw, Check } from 'lucide-react';
import { Sheet, SheetPortal, SheetOverlay, SheetClose, SheetTitle, SheetDescription } from './ui/sheet';
import * as SheetPrimitive from '@radix-ui/react-dialog';

export const OptionsOverlay = ({ open, options, value, onChange, onClose, label, emptyMessage }) => {
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <SheetPortal>
        <SheetOverlay className="fixed inset-0 z-[9999] bg-black/40" />
        <SheetPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-[9999] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[calc(100dvh-120px)] flex flex-col outline-none animate-in slide-in-from-bottom duration-200"
          style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
          dir="rtl"
        >
          <SheetTitle className="sr-only">{label || 'בחר אפשרות'}</SheetTitle>
          <SheetDescription className="sr-only">בחירת ערך מתוך רשימת אפשרויות</SheetDescription>
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
            <SheetClose asChild>
              <button type="button" className="p-1 text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </SheetClose>
            <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
            <div className="w-6" />
          </div>
          <div className="overflow-y-auto flex-1 overscroll-contain">
            {options.length === 0 ? (
              <div className="px-4 py-8 text-sm text-slate-400 text-center">
                {emptyMessage || 'אין אפשרויות'}
              </div>
            ) : (
              options.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { onChange(opt.value); onClose(); }}
                  className={`w-full px-4 py-3 text-sm text-right flex items-center justify-between border-b border-slate-100 last:border-0 active:bg-amber-50 ${opt.value === value ? 'bg-amber-50 text-amber-700 font-medium' : 'text-slate-700'}`}
                >
                  {opt.label}
                  {opt.value === value && <Check className="w-4 h-4 text-amber-600 flex-shrink-0" />}
                </button>
              ))
            )}
          </div>
        </SheetPrimitive.Content>
      </SheetPortal>
    </Sheet>
  );
};

export const SelectField = ({ label, value, onChange, options, error, icon: Icon, placeholder, isLoading, disabled, hasError, onRetry, emptyMessage }) => {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find(o => o.value === value)?.label;
  const isDisabled = disabled || isLoading;
  const displayText = isLoading ? 'טוען...' : (disabled ? 'בחר שדה אב קודם' : (selectedLabel || placeholder || 'בחר...'));

  return (
    <div className="space-y-1" dir="rtl">
      {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
      <div className="relative">
        {Icon && <Icon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none z-10" />}
        <button
          type="button"
          onClick={() => { if (!isDisabled) setOpen(true); }}
          className={`w-full ${Icon ? 'pr-10' : 'pr-3'} pl-8 py-2.5 border rounded-lg bg-white text-sm text-right focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${!selectedLabel && !isLoading && !disabled ? 'text-slate-400' : 'text-slate-900'}`}
        >
          {displayText}
        </button>
        {isLoading ? (
          <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-amber-500 animate-spin pointer-events-none" />
        ) : (
          <ChevronDown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        )}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {!isLoading && !disabled && !hasError && options.length === 0 && emptyMessage && (
        <p className="text-xs text-slate-500 mt-1">{emptyMessage}</p>
      )}
      {hasError && onRetry && (
        <button type="button" onClick={onRetry}
          className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 mt-1">
          <RefreshCw className="w-3 h-3" />
          שגיאה בטעינה - לחץ לנסות שוב
        </button>
      )}
      <OptionsOverlay
        open={open}
        options={options}
        value={value}
        onChange={onChange}
        onClose={() => setOpen(false)}
        label={label}
        emptyMessage={emptyMessage}
      />
    </div>
  );
};
