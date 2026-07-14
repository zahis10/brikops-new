import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ArrowDown, ArrowUp, BookOpen, Loader2, Plus, Trash2, X } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { safetyService } from '../../services/api';

// Batch safety-ind1 — org-level induction content editor (owner/org_admin).
// modal={false} is MANDATORY (house rule): modal={true} can leave
// pointer-events:none stuck on <body> in the mobile WebView.
// Dirty-close guard WITHOUT window.confirm (banned): first close click shows
// an inline notice; only a second click actually closes.

const emptySection = () => ({ title: '', body: '' });

const sectionsEqual = (a, b) => {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].title !== b[i].title || a[i].body !== b[i].body) return false;
  }
  return true;
};

// ind2-fix1: template is keyed by the PROJECT's org — the same key the
// conduct ceremony reads. projectId is REQUIRED.
export default function InductionTemplateEditor({ projectId, open, onOpenChange }) {
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(null);
  const [sections, setSections] = useState([]);
  const [loadedSections, setLoadedSections] = useState([]);
  const [saving, setSaving] = useState(false);
  const [starterLoading, setStarterLoading] = useState(false);
  const [closeArmed, setCloseArmed] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCloseArmed(false);
    setLoading(true);
    safetyService.getInductionTemplate(projectId)
      .then((data) => {
        const tpl = data?.template;
        const secs = tpl?.languages?.he?.sections || [];
        setVersion(tpl?.version ?? null);
        setSections(secs.map((s) => ({ ...s })));
        setLoadedSections(secs.map((s) => ({ ...s })));
      })
      .catch((err) => {
        toast.error(err.response?.data?.detail || 'שגיאה בטעינת תוכן ההדרכה');
      })
      .finally(() => setLoading(false));
  }, [open]);

  const dirty = !sectionsEqual(sections, loadedSections);

  const requestClose = () => {
    if (dirty && !closeArmed) {
      setCloseArmed(true);
      return;
    }
    onOpenChange(false);
  };

  const updateSection = (idx, field, value) => {
    setCloseArmed(false);
    setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  };

  const moveSection = (idx, dir) => {
    setCloseArmed(false);
    setSections((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  };

  const removeSection = (idx) => {
    setCloseArmed(false);
    setSections((prev) => prev.filter((_, i) => i !== idx));
  };

  const addSection = () => {
    setCloseArmed(false);
    setSections((prev) => [...prev, emptySection()]);
  };

  const loadStarter = async () => {
    setStarterLoading(true);
    try {
      const data = await safetyService.getInductionStarter();
      setSections((data?.sections || []).map((s) => ({ ...s })));
      setCloseArmed(false);
      toast.info('התבנית לדוגמה נטענה — יש ללחוץ שמירה כדי לשמור');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בטעינת התבנית לדוגמה');
    } finally {
      setStarterLoading(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const data = await safetyService.saveInductionTemplate(projectId, sections);
      const tpl = data?.template;
      const secs = tpl?.languages?.he?.sections || [];
      setVersion(tpl?.version ?? null);
      setSections(secs.map((s) => ({ ...s })));
      setLoadedSections(secs.map((s) => ({ ...s })));
      setCloseArmed(false);
      toast.success(`נשמר · גרסה ${tpl?.version}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שמירת תוכן ההדרכה נכשלה');
    } finally {
      setSaving(false);
    }
  };

  const emptyState = !loading && sections.length === 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => { if (!v) requestClose(); else onOpenChange(v); }}
      modal={false}
    >
      <DialogContent
        dir="rtl"
        className="max-w-2xl w-[calc(100%-2rem)] p-0 gap-0 overflow-hidden [&>button]:hidden"
        onInteractOutside={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="bg-slate-900 text-white px-5 py-4 flex flex-row items-center justify-between space-y-0">
          <button
            type="button"
            className="p-1 rounded-lg hover:bg-slate-700 transition-colors"
            aria-label="סגור"
            onClick={requestClose}
          >
            <X className="w-5 h-5" />
          </button>
          <DialogTitle className="text-base font-bold text-right flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            תוכן הדרכת אתר
            {version != null && (
              <span className="text-xs font-normal text-slate-300">גרסה {version}</span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-10 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          )}

          {emptyState && (
            <div className="border border-dashed border-slate-300 rounded-xl p-6 text-center space-y-3">
              <p className="text-sm text-slate-600">
                עדיין לא הוגדר תוכן הדרכת אתר לארגון. אפשר להתחיל מתבנית לדוגמה
                ולערוך אותה, או להוסיף סעיפים ידנית.
              </p>
              <Button type="button" variant="outline" onClick={loadStarter} disabled={starterLoading}>
                {starterLoading && <Loader2 className="w-4 h-4 ml-1 animate-spin" />}
                טען תבנית לדוגמה
              </Button>
            </div>
          )}

          {!loading && sections.map((s, idx) => (
            <div key={idx} className="border border-slate-200 rounded-xl p-3 space-y-2 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-400 shrink-0 w-6 text-center">{idx + 1}</span>
                <Input
                  value={s.title}
                  onChange={(e) => updateSection(idx, 'title', e.target.value)}
                  placeholder="כותרת הסעיף"
                  maxLength={200}
                  className="bg-white"
                />
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200 disabled:opacity-30"
                    aria-label="הזז למעלה"
                    disabled={idx === 0}
                    onClick={() => moveSection(idx, -1)}
                  >
                    <ArrowUp className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200 disabled:opacity-30"
                    aria-label="הזז למטה"
                    disabled={idx === sections.length - 1}
                    onClick={() => moveSection(idx, 1)}
                  >
                    <ArrowDown className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    className="p-1.5 rounded-lg text-red-500 hover:bg-red-50"
                    aria-label="מחק סעיף"
                    onClick={() => removeSection(idx)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <Textarea
                value={s.body}
                onChange={(e) => updateSection(idx, 'body', e.target.value)}
                placeholder="תוכן הסעיף"
                maxLength={5000}
                rows={3}
                className="bg-white"
              />
            </div>
          ))}

          {!loading && (
            <Button type="button" variant="outline" className="w-full" onClick={addSection}>
              <Plus className="w-4 h-4 ml-1" />
              הוסף סעיף
            </Button>
          )}
        </div>

        <DialogFooter className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex flex-row-reverse items-center gap-2 sm:justify-start">
          <Button
            type="button"
            onClick={save}
            disabled={saving || loading || sections.length === 0}
            className="min-h-[44px] min-w-[96px]"
          >
            {saving && <Loader2 className="w-4 h-4 ml-1 animate-spin" />}
            שמור
          </Button>
          <Button type="button" variant="outline" disabled={saving} className="min-h-[44px]" onClick={requestClose}>
            סגור
          </Button>
          {closeArmed && dirty && (
            <p className="text-xs text-amber-600 font-medium flex-1 text-right">
              יש שינויים שלא נשמרו — לחץ שוב לסגירה
            </p>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
