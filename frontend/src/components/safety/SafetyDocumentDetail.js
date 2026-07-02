import React from 'react';
import { X, Camera } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { CATEGORY_HE, SEVERITY_HE, DOC_STATUS_HE } from './safetyLabels';

// Read-only detail view for a safety document. Mirrors SafetyFormModal's chrome
// (Dialog modal={false} + outside-close prevention + [&>button]:hidden) but
// renders no form — pure presentation of the passed `doc`. No network, no writes.
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800',
  '2': 'bg-amber-100 text-amber-800',
  '3': 'bg-red-100 text-red-800',
};

const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

function Field({ label, children }) {
  if (children == null || children === '') return null;
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <div className="text-sm text-slate-900">{children}</div>
    </div>
  );
}

export default function SafetyDocumentDetail({
  doc, open, onClose, isWriter, companies = [], onEdit,
}) {
  if (!doc) return null;

  const companyName = doc.company_id
    ? (companies.find((c) => c.id === doc.company_id)?.name
      || companies.find((c) => c.id === doc.company_id)?.company_name
      || null)
    : null;

  const photos = (doc.photo_display_urls || []).filter(isHttp);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }} modal={false}>
      <DialogContent
        dir="rtl"
        className="max-w-lg w-[calc(100%-2rem)] p-0 gap-0 overflow-hidden [&>button]:hidden"
        onInteractOutside={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="bg-slate-900 text-white px-5 py-4 flex flex-row items-center justify-between space-y-0">
          <DialogClose asChild>
            <button type="button" className="p-1 rounded-lg hover:bg-slate-700 transition-colors" aria-label="סגור">
              <X className="w-5 h-5" />
            </button>
          </DialogClose>
          <DialogTitle className="text-base font-bold text-right">פרטי ליקוי</DialogTitle>
        </DialogHeader>

        <div className="px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="flex items-start gap-2">
            <Badge className={SEVERITY_COLOR[doc.severity] || 'bg-slate-100 text-slate-700'}>
              {SEVERITY_HE[doc.severity] || '—'}
            </Badge>
            <h3 className="text-lg font-bold text-slate-900 flex-1 min-w-0">{doc.title}</h3>
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Field label="קטגוריה">{CATEGORY_HE[doc.category] || doc.category}</Field>
            <Field label="סטטוס">{DOC_STATUS_HE[doc.status] || doc.status}</Field>
            <Field label="תאריך גילוי">{(doc.found_at || '').slice(0, 10) || null}</Field>
            <Field label="מיקום">{doc.location || null}</Field>
            <Field label="חברה">{companyName}</Field>
            <Field label="אחראי">{doc.assignee_name || null}</Field>
          </div>

          {doc.description && (
            <Field label="תיאור">
              <p className="whitespace-pre-wrap">{doc.description}</p>
            </Field>
          )}

          {photos.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-slate-500">תמונות</p>
              <div className="grid grid-cols-3 gap-2">
                {photos.map((url, idx) => (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg overflow-hidden border border-slate-200 bg-slate-100"
                  >
                    <img src={url} alt="" className="w-full aspect-square object-cover" />
                  </a>
                ))}
              </div>
            </div>
          )}

          {photos.length === 0 && (
            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <Camera className="w-4 h-4" />
              אין תמונות מצורפות
            </div>
          )}
        </div>

        <DialogFooter className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex flex-row-reverse gap-2 sm:justify-start">
          {isWriter && (
            <Button type="button" onClick={() => onEdit(doc)} className="min-h-[44px] min-w-[96px]">
              ערוך
            </Button>
          )}
          <DialogClose asChild>
            <Button type="button" variant="outline" className="min-h-[44px]">
              סגור
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
