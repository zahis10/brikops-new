import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService } from '../../services/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { TOUR_TYPE_HE } from './safetyLabels';

// Local (not UTC) YYYY-MM-DD so "today" matches the walker's wall clock.
const todayLocal = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

// Small create dialog for a safety tour (batch safety-p2-4b). Picks a type + date
// (+ a name for custom) and POSTs it; the parent opens the runner with the result.
// modal={false} + [&>button]:hidden mirrors the add-chooser chrome (CLAUDE.md).
export default function SafetyTourCreateDialog({ projectId, open, onClose, onCreated }) {
  const [tourType, setTourType] = useState('assistant_morning');
  const [customName, setCustomName] = useState('');
  const [tourDate, setTourDate] = useState(todayLocal());
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTourType('assistant_morning');
    setCustomName('');
    setTourDate(todayLocal());
    setSubmitting(false);
  }, [open]);

  // Client mirror of the server 422: custom must carry a name.
  const customNameMissing = tourType === 'custom' && !customName.trim();
  const canSubmit = !submitting && !!tourDate && !customNameMissing;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    const payload = {
      tour_type: tourType,
      tour_date: tourDate,
      custom_name: tourType === 'custom' ? customName.trim() : null,
    };
    setSubmitting(true);
    try {
      const tour = await safetyService.createTour(projectId, payload);
      onCreated?.(tour);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'יצירת הסיור נכשלה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !submitting) onClose?.(); }} modal={false}>
      <DialogContent
        dir="rtl"
        className="max-w-md w-[calc(100%-2rem)] [&>button]:hidden"
        onInteractOutside={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="text-right">סיור חדש</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>סוג סיור</Label>
            <div className="grid grid-cols-1 gap-2">
              {Object.entries(TOUR_TYPE_HE).map(([val, he]) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setTourType(val)}
                  className={`w-full text-right rounded-xl border-2 px-4 py-3 text-sm font-medium min-h-[52px] transition-colors ${
                    tourType === val
                      ? 'border-blue-500 bg-blue-50 text-blue-800'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {he}
                </button>
              ))}
            </div>
          </div>

          {tourType === 'custom' && (
            <div className="space-y-1.5">
              <Label htmlFor="tour-name">שם הסיור *</Label>
              <Input
                id="tour-name"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                maxLength={120}
                placeholder="לדוגמה: סיור בטיחות ליום גיבוש"
              />
              {customNameMissing && (
                <p className="text-xs text-red-600">יש להזין שם לסיור מותאם</p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="tour-date">תאריך</Label>
            <Input
              id="tour-date"
              type="date"
              value={tourDate}
              onChange={(e) => setTourDate(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter className="flex-row-reverse gap-2 sm:gap-2">
          <Button type="button" className="min-h-[44px]" disabled={!canSubmit} onClick={handleSubmit}>
            {submitting ? 'מתחיל…' : 'התחל סיור'}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="min-h-[44px]"
            disabled={submitting}
            onClick={() => onClose?.()}
          >
            ביטול
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
