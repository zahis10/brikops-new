import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ArrowDown, ArrowUp, BookOpen, Languages, Loader2, Plus, Trash2, X } from 'lucide-react';
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
//
// ind3 E3 — language TABS (he/en/ru/ar/zh). Per-tab editing exactly like the
// he editor; "תרגם אוטומטית מעברית" fills the tab IN MEMORY as a draft
// (nothing persists until שמור). שמור sends the FULL languages map (E2);
// an emptied tab un-fills that language server-side.

const emptySection = () => ({ title: '', body: '' });

const LANGS = [
  { code: 'he', label: 'עברית', dir: 'rtl' },
  { code: 'en', label: 'English', dir: 'ltr' },
  { code: 'ru', label: 'Русский', dir: 'ltr' },
  { code: 'ar', label: 'العربية', dir: 'rtl' },
  { code: 'zh', label: '中文', dir: 'ltr' },
];

const sectionsEqual = (a, b) => {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].title !== b[i].title || a[i].body !== b[i].body) return false;
  }
  return true;
};

const langsEqual = (a, b) => LANGS.every(({ code }) => sectionsEqual(a[code] || [], b[code] || []));

const emptyLangMap = () => ({ he: [], en: [], ru: [], ar: [], zh: [] });

const fromTemplate = (tpl) => {
  const out = emptyLangMap();
  LANGS.forEach(({ code }) => {
    const secs = tpl?.languages?.[code]?.sections || [];
    out[code] = secs.map((s) => ({ ...s }));
  });
  return out;
};

// ind2-fix1: template is keyed by the PROJECT's org — the same key the
// conduct ceremony reads. projectId is REQUIRED.
// ind2-fix3 D2: canEdit=false → read-only view (no inputs/reorder/save/
// starter) + contact notice; dirty-guard only in edit mode.
const READ_ONLY_NOTICE = 'לשינויים יש לפנות לבעל הארגון או למנהל הפרויקט';
const DRAFT_BANNER = 'טיוטת תרגום אוטומטי — עברו על התוכן ותקנו לפני שמירה';

export default function InductionTemplateEditor({ projectId, canEdit = false, open, onOpenChange }) {
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(null);
  const [langs, setLangs] = useState(emptyLangMap());
  const [loadedLangs, setLoadedLangs] = useState(emptyLangMap());
  const [activeLang, setActiveLang] = useState('he');
  const [draftLangs, setDraftLangs] = useState({}); // {code: true} — unsaved auto-translate draft
  const [translating, setTranslating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starterLoading, setStarterLoading] = useState(false);
  const [closeArmed, setCloseArmed] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCloseArmed(false);
    setActiveLang('he');
    setDraftLangs({});
    setLoading(true);
    safetyService.getInductionTemplate(projectId)
      .then((data) => {
        const tpl = data?.template;
        setVersion(tpl?.version ?? null);
        setLangs(fromTemplate(tpl));
        setLoadedLangs(fromTemplate(tpl));
      })
      .catch((err) => {
        toast.error(err.response?.data?.detail || 'שגיאה בטעינת תוכן ההדרכה');
      })
      .finally(() => setLoading(false));
  }, [open, projectId]);

  const dirty = canEdit && !langsEqual(langs, loadedLangs);
  const sections = langs[activeLang] || [];
  const langMeta = LANGS.find((l) => l.code === activeLang) || LANGS[0];

  const requestClose = () => {
    if (dirty && !closeArmed) {
      setCloseArmed(true);
      return;
    }
    onOpenChange(false);
  };

  const setActiveSections = (updater) => {
    setCloseArmed(false);
    setLangs((prev) => ({
      ...prev,
      [activeLang]: typeof updater === 'function' ? updater(prev[activeLang] || []) : updater,
    }));
  };

  const updateSection = (idx, field, value) => {
    setActiveSections((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  };

  const moveSection = (idx, dir) => {
    setActiveSections((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  };

  const removeSection = (idx) => {
    setActiveSections((prev) => prev.filter((_, i) => i !== idx));
  };

  const addSection = () => {
    setActiveSections((prev) => [...prev, emptySection()]);
  };

  const loadStarter = async () => {
    setStarterLoading(true);
    try {
      const data = await safetyService.getInductionStarter();
      setActiveSections((data?.sections || []).map((s) => ({ ...s })));
      setCloseArmed(false);
      toast.info('התבנית לדוגמה נטענה — יש ללחוץ שמירה כדי לשמור');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בטעינת התבנית לדוגמה');
    } finally {
      setStarterLoading(false);
    }
  };

  const translateFromHebrew = async () => {
    if (!(langs.he || []).length) {
      toast.error('אין תוכן בעברית לתרגום');
      return;
    }
    setTranslating(true);
    try {
      const data = await safetyService.translateInductionTemplate(projectId, activeLang);
      setActiveSections((data?.sections || []).map((s) => ({ ...s })));
      setDraftLangs((prev) => ({ ...prev, [activeLang]: true }));
      setCloseArmed(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שירות התרגום נכשל — נסו שוב מאוחר יותר');
    } finally {
      setTranslating(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {};
      LANGS.forEach(({ code }) => {
        payload[code] = { sections: langs[code] || [] };
      });
      const data = await safetyService.saveInductionTemplateLanguages(projectId, payload);
      const tpl = data?.template;
      setVersion(tpl?.version ?? null);
      setLangs(fromTemplate(tpl));
      setLoadedLangs(fromTemplate(tpl));
      setDraftLangs({});
      setCloseArmed(false);
      toast.success(`נשמר · גרסה ${tpl?.version}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שמירת תוכן ההדרכה נכשלה');
    } finally {
      setSaving(false);
    }
  };

  const emptyState = !loading && sections.length === 0;
  const isHe = activeLang === 'he';

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

        {/* ind3 E3 — language tabs (same tabs read-only when canEdit=false) */}
        <div className="px-3 pt-2 border-b border-slate-100 flex items-center gap-1 overflow-x-auto">
          {LANGS.map(({ code, label }) => {
            const filled = (langs[code] || []).length > 0;
            return (
              <button
                key={code}
                type="button"
                onClick={() => { setActiveLang(code); setCloseArmed(false); }}
                className={`relative px-3 py-2 rounded-t-lg text-sm whitespace-nowrap transition-colors ${
                  activeLang === code
                    ? 'bg-slate-100 font-semibold text-slate-900'
                    : 'text-slate-500 hover:bg-slate-50'
                }`}
              >
                {label}
                {filled && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 align-middle" aria-label="יש תוכן" />
                )}
              </button>
            );
          })}
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[62vh] overflow-y-auto" dir={langMeta.dir}>
          {loading && (
            <div className="flex items-center justify-center py-10 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          )}

          {!loading && canEdit && !isHe && (
            <div dir="rtl" className="space-y-2">
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={translateFromHebrew}
                disabled={translating || saving}
              >
                {translating
                  ? <Loader2 className="w-4 h-4 ml-1 animate-spin" />
                  : <Languages className="w-4 h-4 ml-1" />}
                תרגם אוטומטית מעברית
              </Button>
              {draftLangs[activeLang] && (
                <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5">
                  <p className="text-xs text-amber-800 text-center font-medium">{DRAFT_BANNER}</p>
                </div>
              )}
            </div>
          )}

          {emptyState && canEdit && isHe && (
            <div dir="rtl" className="border border-dashed border-slate-300 rounded-xl p-6 text-center space-y-3">
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

          {emptyState && !canEdit && (
            <div dir="rtl" className="border border-dashed border-slate-300 rounded-xl p-6 text-center">
              <p className="text-sm text-slate-600">
                {isHe ? 'טרם הוגדר תוכן הדרכת אתר' : 'אין תוכן בשפה זו'}
              </p>
            </div>
          )}

          {!loading && !canEdit && (
            <>
              {sections.map((s, idx) => (
                <div key={idx} className="border border-slate-200 rounded-xl p-3 space-y-1 bg-slate-50/50">
                  <div className="flex items-start gap-2">
                    <span className="text-xs font-semibold text-slate-400 shrink-0 w-6 text-center pt-0.5">{idx + 1}</span>
                    <p className="text-sm font-semibold text-slate-900">{s.title}</p>
                  </div>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap pr-8">{s.body}</p>
                </div>
              ))}
              {sections.length > 0 && (
                <div dir="rtl" className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-3">
                  <p className="text-xs text-blue-800 text-center">{READ_ONLY_NOTICE}</p>
                </div>
              )}
            </>
          )}

          {!loading && canEdit && sections.map((s, idx) => (
            <div key={idx} className="border border-slate-200 rounded-xl p-3 space-y-2 bg-slate-50/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-400 shrink-0 w-6 text-center">{idx + 1}</span>
                <Input
                  value={s.title}
                  onChange={(e) => updateSection(idx, 'title', e.target.value)}
                  placeholder="כותרת הסעיף"
                  maxLength={200}
                  className="bg-white"
                  dir={langMeta.dir}
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
                dir={langMeta.dir}
              />
            </div>
          ))}

          {!loading && canEdit && (
            <Button type="button" variant="outline" className="w-full" onClick={addSection}>
              <Plus className="w-4 h-4 ml-1" />
              הוסף סעיף
            </Button>
          )}
        </div>

        <DialogFooter className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex flex-row-reverse items-center gap-2 sm:justify-start">
          {canEdit && (
            <Button
              type="button"
              onClick={save}
              disabled={saving || loading || (langs.he || []).length === 0}
              className="min-h-[44px] min-w-[96px]"
            >
              {saving && <Loader2 className="w-4 h-4 ml-1 animate-spin" />}
              שמור
            </Button>
          )}
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
