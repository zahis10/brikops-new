import React, { useEffect } from 'react';
import { ChevronLeft, X } from 'lucide-react';

export default function DefectPhotoPreview({ task, onClose, onOpen }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div dir="rtl" className="fixed inset-0 z-[60] bg-black/90 flex flex-col">
      <div className="p-3 flex items-center justify-between gap-2">
        <p className="text-sm font-bold text-white truncate">{task.title}</p>
        <button type="button" onClick={onClose} aria-label="סגור"
          className="min-h-[44px] min-w-[44px] flex items-center justify-center text-white">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 flex items-center justify-center p-2" onClick={onClose}>
        <img src={task.image_url} alt={task.title}
          className="max-h-full max-w-full object-contain rounded-lg"
          onClick={(event) => event.stopPropagation()} />
      </div>
      <div className="p-3 flex items-center justify-between gap-2">
        {task.image_count > 1 && <span className="text-xs text-white/70">
          עוד {task.image_count - 1} תמונות בליקוי
        </span>}
        <button type="button" onClick={onOpen}
          className="min-h-[44px] px-4 rounded-lg bg-amber-500 font-bold text-white flex items-center gap-1">
          לליקוי <ChevronLeft className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}