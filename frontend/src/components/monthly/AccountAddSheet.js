import React, { useEffect, useState } from 'react';
import { House, Ruler } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';

export default function AccountAddSheet({ open, onOpenChange, contractor, onUnits, onTerms, onMeasured }) {
  const [choice, setChoice] = useState(null);
  const stages = contractor.stages || [];
  useEffect(() => { if (open) setChoice(null); }, [open]);
  const chooseStage = (stage) => {
    if (choice === 'units') onUnits(stage);
    else onTerms(stage);
    onOpenChange(false);
  };
  const options = [
    { id: 'units', icon: <House className="h-5 w-5" />, title: 'לסמן דירות שבוצעו',
      description: 'בוחרים שלב, בניין וקומה ומסמנים דירות — נרשם במטריצה' },
    { id: 'measured', icon: <Ruler className="h-5 w-5" />, title: 'להוסיף עבודה שלא במטריצה',
      description: 'קירות תמך, חפירה… מקלידים כמה בוצע החודש' },
    { id: 'terms', icon: '₪', title: 'להגדיר מה משלמים על שלב',
      description: 'סכום קבוע לדירה או לפי כמות — פעם אחת לכל שלב' },
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[90vh] overflow-y-auto text-right" aria-describedby={undefined}>
        <DialogHeader className="text-right">
          <DialogTitle>{`מה להוסיף לחשבון של ${contractor.name}?`}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          {options.map((option) => {
            const disabled = option.id !== 'measured' && !stages.length;
            return <button key={option.id} type="button" disabled={disabled}
              aria-pressed={choice === option.id}
              onClick={() => {
                if (option.id === 'measured') { onMeasured(); onOpenChange(false); }
                else setChoice(option.id);
              }}
              className={`min-h-[56px] w-full rounded-xl border border-slate-200 bg-white p-3 text-right flex items-center gap-3 disabled:opacity-50${choice === option.id ? ' border-2 border-amber-400 bg-amber-50' : choice ? ' opacity-50' : ''}`}>
              <span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-800" aria-hidden="true">{option.icon}</span>
              <span><strong className="block text-sm text-slate-900">{option.title}</strong>
                <span className="text-xs text-slate-500">{disabled ? 'אין שלבים משויכים לקבלן' : option.description}</span></span>
            </button>;
          })}
        </div>
        {choice && <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-3">
          <p className="mb-2 text-base font-bold text-amber-800">{choice === 'units' ? 'באיזה שלב לסמן דירות?' : 'על איזה שלב להגדיר תשלום?'}</p>
          <div className="flex flex-wrap gap-2">
            {stages.map((stage) => <button key={stage.stage_id} type="button" onClick={() => chooseStage(stage)}
              className="min-h-[44px] rounded-full border border-amber-300 bg-white px-3 text-sm font-bold text-amber-800">{stage.title}</button>)}
          </div>
        </div>}
      </DialogContent>
    </Dialog>
  );
}
