import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight, NotebookPen, ChevronRight, ChevronLeft, CalendarOff, Plus,
} from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { diaryService, projectService } from '../services/api';
import WorkDiaryEntryView from '../components/diary/WorkDiaryEntryView';
import { STATUS_HE, NO_WORK_REASONS } from '../components/diary/diaryLabels';

// Writers = the two project roles the diary backend accepts for create/edit
// (work_diary_router uses safety's SAFETY_WRITERS). Same gating convention as
// SafetyHomePage — owner/admin get read-only.
const DIARY_WRITERS = ['project_manager', 'management_team'];

// Israel-local YYYY-MM-DD — matches the backend's israel_today() day boundary.
const todayIL = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Jerusalem' });

const monthLabel = (month) => {
  const d = new Date(`${month}-01T00:00:00`);
  return d.toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
};

const shiftMonth = (month, delta) => {
  const [y, m] = month.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

export default function WorkDiaryPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const dateParam = searchParams.get('date');

  const [project, setProject] = useState(null);
  const [entries, setEntries] = useState({ items: [], total: 0 });
  const [month, setMonth] = useState(() => todayIL().slice(0, 7));
  const [loading, setLoading] = useState(true);
  const [flagOff, setFlagOff] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [creating, setCreating] = useState(false);
  const [noWorkOpen, setNoWorkOpen] = useState(false);
  const [noWorkReason, setNoWorkReason] = useState('');
  const [noWorkText, setNoWorkText] = useState('');

  const isWriter = DIARY_WRITERS.includes(project?.my_role);

  // Deep link (?date= outside the loaded month) → jump the month picker there.
  // The list fetch below then either finds the entry or shows the miss state.
  useEffect(() => {
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam) && dateParam.slice(0, 7) !== month) {
      setMonth(dateParam.slice(0, 7));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateParam]);

  useEffect(() => {
    if (!projectId) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        let proj = null;
        try { proj = await projectService.get(projectId); } catch (e) { /* diary call surfaces status */ }
        if (cancelled) return;
        if (proj) setProject(proj);

        const resp = await diaryService.listEntries(projectId, { month });
        if (cancelled) return;
        setEntries(resp || { items: [], total: 0 });
      } catch (err) {
        if (cancelled) return;
        const status = err?.response?.status;
        if (status === 404) { setFlagOff(true); }
        else if (status === 403) { setForbidden(true); }
        else toast.error('שגיאה בטעינת יומן העבודה');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, month]);

  // URL-state setter — clone-and-set ONE key (the equipCat lesson).
  const setDateParam = (d) => {
    const next = new URLSearchParams(searchParams);
    if (d) next.set('date', d); else next.delete('date');
    setSearchParams(next);
  };

  const backToControl = () => navigate(`/projects/${projectId}/control?workMode=structure`);

  const reloadMonth = async () => {
    const resp = await diaryService.listEntries(projectId, { month });
    setEntries(resp || { items: [], total: 0 });
    return resp?.items || [];
  };

  const openToday = async () => {
    const today = todayIL();
    if (today.slice(0, 7) === month) {
      const existing = entries.items.find((e) => e.diary_date === today);
      if (existing) { setDateParam(today); return; }
    }
    setCreating(true);
    try {
      await diaryService.createEntry(projectId, { diary_date: today });
      if (today.slice(0, 7) !== month) setMonth(today.slice(0, 7));
      else await reloadMonth();
      setDateParam(today);
    } catch (err) {
      if (err?.response?.status === 409) {
        // double-tap / created elsewhere — just open the existing entry
        if (today.slice(0, 7) !== month) setMonth(today.slice(0, 7));
        else await reloadMonth().catch(() => {});
        setDateParam(today);
      } else {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'שגיאה ביצירת יומן');
      }
    } finally {
      setCreating(false);
    }
  };

  const createNoWork = async () => {
    const reason = noWorkReason === 'אחר' ? noWorkText.trim() : noWorkReason;
    if (!reason) { toast.error('בחר סיבה'); return; }
    const today = todayIL();
    setCreating(true);
    try {
      await diaryService.createEntry(projectId, { diary_date: today, no_work: true, no_work_reason: reason });
      setNoWorkOpen(false);
      setNoWorkReason(''); setNoWorkText('');
      if (today.slice(0, 7) !== month) setMonth(today.slice(0, 7));
      else await reloadMonth();
      setDateParam(today);
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'שגיאה ביצירת יומן');
      if (err?.response?.status === 409) {
        setNoWorkOpen(false);
        await reloadMonth().catch(() => {});
        setDateParam(today);
      }
    } finally {
      setCreating(false);
    }
  };

  const onEntryChanged = (updated) => {
    if (!updated?.id) return;
    setEntries((prev) => ({
      ...prev,
      items: prev.items.map((it) => (it.id === updated.id ? updated : it)),
    }));
  };

  if (forbidden) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
        <NotebookPen className="w-12 h-12 text-amber-500 mb-3" />
        <h2 className="text-lg font-bold text-slate-900">אין הרשאה לצפייה ביומן העבודה</h2>
        <button onClick={backToControl} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm" type="button">
          חזור לדאשבורד
        </button>
      </div>
    );
  }
  if (flagOff) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
        <NotebookPen className="w-12 h-12 text-slate-400 mb-3" />
        <h2 className="text-lg font-bold text-slate-900">מודול יומן העבודה אינו פעיל</h2>
        <p className="text-sm text-slate-600 mt-2">צור קשר עם התמיכה להפעלה.</p>
        <button onClick={backToControl} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm" type="button">
          חזור לדאשבורד
        </button>
      </div>
    );
  }

  // ---------- ENTRY VIEW ----------
  if (dateParam) {
    const entry = entries.items.find((e) => e.diary_date === dateParam);
    if (loading) {
      return (
        <div dir="rtl" className="min-h-screen bg-slate-50 flex items-center justify-center">
          <p className="text-sm text-slate-500">טוען…</p>
        </div>
      );
    }
    if (!entry) {
      return (
        <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
          <CalendarOff className="w-12 h-12 text-slate-400 mb-3" />
          <h2 className="text-lg font-bold text-slate-900">לא נמצא יומן לתאריך זה</h2>
          <button onClick={() => setDateParam(null)} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm" type="button">
            חזרה לרשימה
          </button>
        </div>
      );
    }
    return (
      <WorkDiaryEntryView
        projectId={projectId}
        entry={entry}
        isWriter={isWriter}
        onChanged={onEntryChanged}
        onBack={() => setDateParam(null)}
      />
    );
  }

  // ---------- LIST VIEW ----------
  const today = todayIL();
  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 pb-24">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="flex items-center gap-2 px-4 py-3">
          <button onClick={backToControl} className="p-2 rounded-lg hover:bg-slate-100" aria-label="חזור" type="button">
            <ArrowRight className="w-5 h-5 text-slate-700" />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-slate-900 truncate">יומן עבודה</h1>
            {project?.name && <p className="text-xs text-slate-500 truncate">{project.name}</p>}
          </div>
        </div>
        <div className="flex items-center justify-between px-4 pb-3">
          <button
            onClick={() => setMonth(shiftMonth(month, 1))}
            className="p-1.5 rounded-lg hover:bg-slate-100"
            aria-label="חודש הבא"
            type="button"
          >
            <ChevronRight className="w-5 h-5 text-slate-600" />
          </button>
          <span className="text-sm font-medium text-slate-800">{monthLabel(month)}</span>
          <button
            onClick={() => setMonth(shiftMonth(month, -1))}
            className="p-1.5 rounded-lg hover:bg-slate-100"
            aria-label="חודש קודם"
            type="button"
          >
            <ChevronLeft className="w-5 h-5 text-slate-600" />
          </button>
        </div>
      </header>

      <main className="p-4 space-y-3 max-w-2xl mx-auto">
        {isWriter && (
          <div className="flex gap-2">
            <Button onClick={openToday} disabled={creating} className="flex-1 gap-1.5">
              <Plus className="w-4 h-4" />
              יומן היום
            </Button>
            <Button variant="outline" onClick={() => setNoWorkOpen(true)} disabled={creating} className="gap-1.5">
              <CalendarOff className="w-4 h-4" />
              לא עבדו היום
            </Button>
          </div>
        )}

        {loading ? (
          <p className="text-sm text-slate-500 text-center py-10">טוען…</p>
        ) : !entries.items.length ? (
          <div className="text-center py-12">
            <NotebookPen className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">אין רשומות יומן בחודש זה</p>
          </div>
        ) : (
          <Card className="divide-y divide-slate-100 overflow-hidden">
            {entries.items.map((e) => {
              const d = new Date(`${e.diary_date}T00:00:00`);
              return (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => setDateParam(e.diary_date)}
                  className="w-full text-right px-4 py-3 hover:bg-slate-50 block"
                >
                  <div className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900">
                        {d.toLocaleDateString('he-IL', { weekday: 'long', day: 'numeric', month: 'long' })}
                        {e.diary_date === today && <span className="text-xs text-slate-500"> · היום</span>}
                      </p>
                      {e.work_description && (
                        <p className="text-xs text-slate-500 truncate mt-0.5">
                          {e.work_description.split('\n')[0]}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {e.entered_late && (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full border border-red-300 text-red-600">
                          הוזן באיחור
                        </span>
                      )}
                      {e.no_work && (
                        <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600">
                          לא עבדו
                        </span>
                      )}
                      <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${e.status === 'signed' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
                        {STATUS_HE[e.status] || e.status}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </Card>
        )}
      </main>

      <Dialog open={noWorkOpen} onOpenChange={(o) => { if (!creating) setNoWorkOpen(o); }}>
        <DialogContent dir="rtl" className="max-w-sm">
          <DialogHeader>
            <DialogTitle>לא עבדו היום</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Select value={noWorkReason} onValueChange={setNoWorkReason} dir="rtl">
              <SelectTrigger><SelectValue placeholder="בחר סיבה" /></SelectTrigger>
              <SelectContent>
                {NO_WORK_REASONS.map((r) => (
                  <SelectItem key={r} value={r}>{r}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {noWorkReason === 'אחר' && (
              <Input
                value={noWorkText}
                onChange={(e) => setNoWorkText(e.target.value)}
                placeholder="פרט את הסיבה"
                maxLength={120}
              />
            )}
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setNoWorkOpen(false)} disabled={creating}>ביטול</Button>
            <Button onClick={createNoWork} disabled={creating}>
              {creating ? 'יוצר…' : 'צור רשומה'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
