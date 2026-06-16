import React from 'react';
import { Loader2, X } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from '../ui/dialog';
import { Button } from '../ui/button';

// Shared, entity-agnostic shell for the Safety create/edit forms.
// modal={false} is MANDATORY (CLAUDE.md): modal={true} can leave
// pointer-events:none stuck on <body> if the dialog unmounts mid-animation
// inside the mobile WebView. The forms pass their fields as children and own
// all entity logic; this shell only renders the chrome + footer.
export default function SafetyFormModal({
  open, onOpenChange, title, children, onSubmit, submitting, submitLabel = 'שמור',
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} modal={false}>
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
          <DialogTitle className="text-base font-bold text-right">{title}</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
          className="flex flex-col"
        >
          <div className="px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
            {children}
          </div>

          <DialogFooter className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex flex-row-reverse gap-2 sm:justify-start">
            <Button type="submit" disabled={submitting} className="min-h-[44px] min-w-[96px]">
              {submitting && <Loader2 className="w-4 h-4 ml-1 animate-spin" />}
              {submitLabel}
            </Button>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={submitting} className="min-h-[44px]">
                ביטול
              </Button>
            </DialogClose>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
