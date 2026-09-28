import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarCheck, ChevronLeft } from 'lucide-react';
import { monthlyCloseService } from '../../services/monthlyCloseService';

const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

export default function MonthlyCloseCard({ projectId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setData(null);
    setLoading(true);
    const load = async () => {
      try {
        const list = await monthlyCloseService.getMonths(projectId);
        if (!active) return;
        const month = list.next_closable <= list.current_month ? list.next_closable : list.current_month;
        const account = await monthlyCloseService.getMonth(projectId, month);
        if (active) setData({ list, account });
      } catch {
        if (active) setData(null);
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [projectId]);

  if (loading) return <div role="status" aria-label="טוען חשבון חודשי" className="h-20 rounded-xl bg-slate-200 animate-pulse" />;
  if (!data) return null;
  const { list, account } = data;
  const total = account.totals?.stages ?? 0;
  if (account.permissions?.role === 'contractor' || total === 0) return null;
  const unmapped = account.unmapped_stages?.length ?? 0;
  const mapped = Math.max(0, total - unmapped);
  const companies = account.contractors?.filter((company) => company.stages?.length).length ?? 0;
  const canWrite = !!account.permissions?.can_write;
  const overdue = account.status === 'open' && account.month < list.current_month;
  const target = `/projects/${projectId}/monthly-close?month=${account.month}`;
  const back = { state: { returnTo: `/projects/${projectId}/dashboard` } };

  return (
    <div className="bg-white rounded-xl border shadow-sm p-4">
      <div className="flex items-center gap-2 mb-2">
        <CalendarCheck className="w-4 h-4 text-amber-500" />
        <h3 className="text-sm font-bold text-slate-700">חשבון חודשי</h3>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold text-slate-800">{account.label}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${
          account.status === 'closed' ? 'bg-emerald-100 text-emerald-700' :
            overdue ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'
        }`}>
          {account.status === 'closed'
            ? `נסגר ${dayMonth(account.closed_at)} · ${account.closed_by?.name}`
            : overdue ? 'עדיין לא נסגר' : 'פתוח'}
        </span>
      </div>
      <div className="mt-2 text-sm text-slate-700">
        {account.kpis?.this_month ?? 0} שלבי-דירה {account.status === 'closed' ? 'בחשבון' : 'בוצעו החודש'} · {companies} קבלנים
      </div>
      {canWrite && account.status === 'open' && (
        <div className={`mt-1 text-xs ${unmapped > 0 ? 'text-amber-800' : 'text-slate-500'}`}>
          {unmapped > 0
            ? `${unmapped} שלבים ללא קבלן — לא ייכנסו לאף חשבון`
            : `${mapped}/${total} שלבים משויכים לקבלנים`}
        </div>
      )}
      <button onClick={() => navigate(target, back)}
        className={`mt-3 min-h-[44px] w-full sm:w-auto px-4 rounded-lg font-bold flex items-center justify-center gap-1 ${
          canWrite && account.status === 'open' && (overdue || unmapped > 0)
            ? 'bg-amber-500 text-white' : 'border border-amber-300 text-amber-800'
          }`}>
        {canWrite && overdue ? `לסגירת חשבון ${account.label}` : 'לדף החשבונות'}
        <ChevronLeft className="w-4 h-4" />
      </button>
    </div>
  );
}