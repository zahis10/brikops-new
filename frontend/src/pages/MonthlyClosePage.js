import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowRight, CalendarCheck, ChevronLeft, ChevronRight, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { monthlyCloseService } from '../services/monthlyCloseService';
import { downloadBlob } from '../utils/fileDownload';
import ContractorAccountCard from '../components/monthly/ContractorAccountCard';
import MonthlySettingsSheet from '../components/monthly/MonthlySettingsSheet';
import CloseMonthDialog from '../components/monthly/CloseMonthDialog';

const MONTHS = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];
const monthLabel = (month) => /^\d{4}-(0[1-9]|1[0-2])$/.test(month || '') ?
  `${MONTHS[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}` : '';
const shiftMonth = (month, delta) => {
  const year = Number(month.slice(0, 4));
  const index = Number(month.slice(5)) - 1 + delta;
  const normalizedYear = year + Math.floor(index / 12);
  return `${normalizedYear}-${String(((index % 12) + 12) % 12 + 1).padStart(2, '0')}`;
};
const monthIndex = (month) => Number(month.slice(0, 4)) * 12 + Number(month.slice(5));
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

export default function MonthlyClosePage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const requestedMonth = params.get('month');
  const [months, setMonths] = useState(null);
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setAccount(null);
    const load = async () => {
      try {
        const list = await monthlyCloseService.getMonths(projectId);
        if (!active) return;
        setMonths(list);
        const month = requestedMonth && /^\d{4}-(0[1-9]|1[0-2])$/.test(requestedMonth)
          ? requestedMonth : (list.next_closable || list.current_month);
        if (!month) throw new Error('לא נמצא חודש להצגה');
        if (month !== requestedMonth) setParams({ month }, { replace: true });
        const result = await monthlyCloseService.getMonth(projectId, month);
        if (active) setAccount(result);
      } catch (err) {
        if (active) {
          setAccount(null);
          setError(err.response?.data?.detail || err.message || 'לא ניתן לטעון את החשבון');
          toast.error(err.response?.data?.detail || 'לא ניתן לטעון את החשבון');
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [projectId, requestedMonth, revision, setParams]);
  const exportCompany = async (companyId) => {
    const { blob, filename } = await monthlyCloseService.exportXlsx(projectId, account.month, companyId);
    await downloadBlob(blob, filename, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  };
  const onClosed = () => {
    toast.success(`${account.label} נסגר`);
    refresh();
  };
  const changeMonth = (delta) => setParams({ month: shiftMonth(account.month, delta) });
  const canWrite = !!account?.permissions?.can_write;
  const contractorView = account?.permissions?.role === 'contractor';
  const contractor = account?.contractors?.[0];
  const hasVisibleBaseline = !!account?.baseline_keys?.length && (!contractorView ||
    account.baseline_keys.some(([stageId]) => contractor?.stages?.some((stage) => stage.stage_id === stageId)));
  const currentMonth = months?.current_month;
  return (
    <div className="min-h-screen bg-slate-50 pb-32" dir="rtl">
      <main className="mx-auto max-w-2xl p-4 sm:p-6">
        <div className="mb-4 flex items-center gap-3">
          <button type="button" onClick={() => navigate(`/projects/${projectId}/execution-matrix`)}
            aria-label="חזרה למטריצת ביצוע" className="rounded-lg p-2 hover:bg-slate-200">
            <ArrowRight className="h-5 w-5" />
          </button>
          <div className="flex-1 rounded-2xl bg-gradient-to-l from-amber-500 to-orange-400 p-4 text-white shadow-sm">
            <div className="flex items-center gap-2">
              <CalendarCheck className="h-6 w-6" />
              <h1 className="text-xl font-bold">חשבון חודשי</h1>
            </div>
            <p className="mt-1 text-sm text-white/90">
              {account?.project?.name || account?.project_name || ''}
              {account?.totals && ` · ${account.totals.units} דירות · ${account.totals.stages} שלבים`}
            </p>
          </div>
          {canWrite && <button type="button" onClick={() => setSettingsOpen(true)} title="הגדרות חשבון חודשי"
            aria-label="הגדרות חשבון חודשי" className="rounded-lg p-2 hover:bg-slate-200">
            <Settings className="h-5 w-5" />
          </button>}
        </div>
        {loading && <div role="status" className="space-y-3 animate-pulse" aria-label="טוען חשבון">
          <div className="h-14 rounded-xl bg-slate-200" /><div className="h-24 rounded-xl bg-slate-200" />
          <div className="h-52 rounded-xl bg-slate-200" />
        </div>}
        {!loading && error && <div className="rounded-xl border border-red-200 bg-white p-5 text-red-700">
          <p>{error}</p><button type="button" onClick={refresh} className="mt-3 font-semibold underline">נסה שוב</button>
        </div>}
        {!loading && account && <>
          <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <button type="button" aria-label="חודש קודם" onClick={() => changeMonth(-1)}
              disabled={monthIndex(account.month) <= monthIndex(shiftMonth(currentMonth || account.month, -24))}
              className="min-h-[44px] rounded-lg px-2 disabled:opacity-30"><ChevronRight className="h-5 w-5" /></button>
            <div className="text-center">
              <strong>{account.label || monthLabel(account.month)}</strong>
              <span className={`mr-2 rounded-full px-2 py-1 text-xs font-bold ${account.status === 'closed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                {account.status === 'closed'
                  ? `נסגר ${dayMonth(account.closed_date_il || account.closed_at)} · ${account.closed_by?.name || ''}` : 'פתוח'}
              </span>
            </div>
            <button type="button" aria-label="חודש הבא" onClick={() => changeMonth(1)}
              disabled={monthIndex(account.month) >= monthIndex(currentMonth || account.month)}
              className="min-h-[44px] rounded-lg px-2 disabled:opacity-30"><ChevronLeft className="h-5 w-5" /></button>
          </div>
          {contractorView && <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            מבט הקבלן — קריאה בלבד: אתה רואה רק את הדוח של {contractor?.name || ''}
          </div>}
          {account.status === 'open' && !account.closable && <div className="mb-4 rounded-xl bg-slate-100 p-3 text-sm text-slate-600">
            {account.last_closed && account.month <= account.last_closed
              ? 'חודש זה לא נסגר ב-BrikOps'
              : `תצוגה מקדימה — הסגירה תתאפשר אחרי ${monthLabel(account.next_closable)}`}
          </div>}
          <div className="mb-4 grid grid-cols-3 gap-2">
            {[
              [account.kpis?.this_month, 'שלבי-דירה בוצעו החודש'],
              [account.kpis?.qc, 'אושרו בבקרת ביצוע'],
              [account.kpis?.manual, 'סומנו ידנית במטריצה'],
            ].map(([value, text]) => <div key={text} className="rounded-xl border border-slate-200 bg-white p-3 text-center shadow-sm">
              <strong className="block text-2xl text-slate-900">{value || 0}</strong>
              <span className="text-xs text-slate-500">{text}</span>
            </div>)}
          </div>
          {hasVisibleBaseline && <p className="mb-4 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600">
            מצטבר קודם — לא נספר בחשבון זה
          </p>}
          {!!account.kpis?.corrections && <p className="mb-4 text-sm font-semibold text-red-700">{account.kpis.corrections} תיקונים מחודש קודם</p>}
          {canWrite && account.status === 'open' && !!account.unmapped_stages?.length && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {account.unmapped_stages.length} שלבים ללא קבלן — לא נכנסים לאף חשבון
              <button type="button" onClick={() => setSettingsOpen(true)} className="mr-2 font-bold underline">שיוך שלבים</button>
            </div>
          )}
          {!account.contractors?.length ? <div className="rounded-xl border border-slate-200 bg-white p-6 text-center">
            <p>{canWrite ? 'עדיין אין שיוך שלבים לקבלנים' : 'אין נתונים לחודש זה'}</p>
            {canWrite && <button type="button" onClick={() => setSettingsOpen(true)}
              className="mt-3 rounded-lg bg-amber-500 px-4 py-2 font-bold text-white">הגדר שיוך</button>}
          </div> : <div className="space-y-3">{account.contractors.map((company) => (
            <ContractorAccountCard key={company.company_id} contractor={company} month={account}
              projectId={projectId} canExport onExport={exportCompany} />
          ))}</div>}
          {canWrite && account.permissions?.can_close && <div className="sticky bottom-3 z-10 mt-6 rounded-xl border border-amber-200 bg-white p-4 shadow-lg">
            <button type="button" onClick={() => setCloseOpen(true)}
              className="min-h-[44px] w-full rounded-lg bg-amber-500 font-bold text-white">
              סגור את {account.label || monthLabel(account.month)}
            </button>
            <p className="mt-2 text-xs text-slate-500">
              אחרי הסגירה החודש קפוא — הדוחות לא משתנים. שלב שייפתח מחדש יופיע ב{monthLabel(shiftMonth(account.month, 1))} כשורת תיקון. הסגירה נרשמת: מי ומתי.
            </p>
          </div>}
        </>}
      </main>
      {canWrite && <MonthlySettingsSheet open={settingsOpen} onOpenChange={setSettingsOpen} projectId={projectId} onSaved={refresh} />}
      {account && <CloseMonthDialog open={closeOpen} onOpenChange={setCloseOpen} projectId={projectId} account={account} onClosed={onClosed} />}
    </div>
  );
}