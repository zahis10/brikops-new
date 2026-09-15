import React, { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { adminAnalyticsService } from '../../services/api';

const WEEKDAYS = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'ש׳'];

function shortDate(date) {
  if (typeof date !== 'string') return '—';
  const parts = date.split('-').map(Number);
  if (parts.length !== 3 || parts.some(part => !Number.isFinite(part))) return '—';
  return `${parts[2]}.${parts[1]}`;
}

function dayLabel(day, today) {
  const weekday = Number(day?.weekday);
  const weekdayText = WEEKDAYS[weekday] || '—';
  const dateText = shortDate(day?.date);
  return day?.date === today ? `היום · יום ${weekdayText} ${dateText}` : `יום ${weekdayText} ${dateText}`;
}

function hourLabel(hour) {
  return String(hour).padStart(2, '0');
}

function cellColor(value, max) {
  if (!value || !max) return 'bg-slate-100 text-slate-400';
  const ratio = value / max;
  if (ratio <= 0.25) return 'bg-emerald-100 text-emerald-800';
  if (ratio <= 0.5) return 'bg-emerald-200 text-emerald-900';
  if (ratio <= 0.75) return 'bg-emerald-300 text-emerald-950';
  if (ratio < 1) return 'bg-emerald-400 text-emerald-950';
  return 'bg-emerald-500 text-white';
}

function peakLabel(peak, days) {
  if (!peak) return 'שעת השיא: אין עדיין נתונים';
  const peakDay = (days || []).find(day => day.date === peak.date);
  const weekday = peakDay ? `יום ${WEEKDAYS[Number(peakDay.weekday)] || '—'} ` : '';
  return `שעת השיא: ${weekday}${shortDate(peak.date)} · ${hourLabel(Number(peak.hour) || 0)}:00 · ${Number(peak.users) || 0} משתמשים`;
}

export default function ActivityHeatmap({ days = 7, orgId = '' }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const requestRef = useRef(0);

  useEffect(() => {
    let mounted = true;
    const requestId = ++requestRef.current;
    const params = { days };
    if (orgId) params.org_id = orgId;

    setLoading(true);
    setError(false);
    setData(null);
    adminAnalyticsService.getHourly(params)
      .then(result => {
        if (!mounted || requestId !== requestRef.current) return;
        setData(result || null);
      })
      .catch(() => {
        if (!mounted || requestId !== requestRef.current) return;
        setError(true);
      })
      .finally(() => {
        if (mounted && requestId === requestRef.current) setLoading(false);
      });

    return () => {
      mounted = false;
      requestRef.current += 1;
    };
  }, [days, orgId, retry]);

  const heatmapDays = Array.isArray(data?.days) ? data.days : [];
  const hourTotals = Array.isArray(data?.hour_totals) ? data.hour_totals : [];
  const max = Math.max(
    Number(data?.max) || 0,
    ...heatmapDays.flatMap(day => Array.isArray(day?.hours) ? day.hours.map(value => Number(value) || 0) : [])
  );
  const today = data?.today;
  const columns = 'minmax(94px, 1fr) repeat(24, minmax(24px, 1fr)) minmax(54px, .7fr)';

  return (
    <section className="w-full min-w-0 max-w-full overflow-hidden rounded-xl border border-slate-200 bg-white" dir="rtl">
      <div className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-bold text-slate-800">פעילות לפי שעות · שעון ישראל</h2>
        <p className="mt-0.5 text-xs text-slate-500">משתמשים שונים שהיו פעילים בכל שעה</p>
      </div>
      <div className="px-4 py-3">
        {loading ? (
          <div className="flex items-center justify-center py-10" aria-label="טוען נתוני שעות">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : error ? (
          <div className="flex flex-wrap items-center justify-center gap-3 py-8 text-sm text-red-600" role="alert">
            <span>לא ניתן לטעון נתוני שעות</span>
            <button
              type="button"
              onClick={() => setRetry(value => value + 1)}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium hover:bg-red-50"
            >
              נסה שוב
            </button>
          </div>
        ) : heatmapDays.length === 0 || max === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">עדיין אין נתוני שעות (נאספים מהיום)</div>
        ) : (
          <>
            <div className="w-full max-w-full overflow-x-auto" dir="ltr" style={{ direction: 'ltr' }}>
              <div className="min-w-[760px] text-[10px]" style={{ display: 'grid', gridTemplateColumns: columns, direction: 'ltr' }}>
                <div className="border-b border-slate-100 px-2 py-1 text-left font-medium text-slate-400">יום</div>
                {Array.from({ length: 24 }, (_, hour) => (
                  <div key={hour} className="border-b border-slate-100 px-0.5 py-1 text-center font-medium text-slate-400">
                    {hourLabel(hour)}
                  </div>
                ))}
                <div className="border-b border-slate-100 px-1 py-1 text-center font-medium text-slate-400">סה״כ</div>

                {heatmapDays.map((day, dayIndex) => {
                  const values = Array.from({ length: 24 }, (_, hour) => Number(day?.hours?.[hour]) || 0);
                  return (
                    <React.Fragment key={day?.date || dayIndex}>
                      <div className="flex min-w-0 items-center border-b border-slate-100 px-2 py-1.5 text-left font-medium text-slate-600" dir="rtl">
                        <span className="truncate">{dayLabel(day, today)}</span>
                      </div>
                      {values.map((value, hour) => (
                        <div
                          key={`${day?.date || dayIndex}-${hour}`}
                          className={`mx-px my-0.5 flex min-h-[24px] items-center justify-center rounded-sm px-0.5 ${cellColor(value, max)}`}
                          title={`${shortDate(day?.date)} · ${hourLabel(hour)}:00 · ${value} משתמשים`}
                        >
                          <span className="hidden md:block">{value || ''}</span>
                        </div>
                      ))}
                      <div className="flex items-center justify-center border-b border-slate-100 font-semibold text-slate-600">
                        {Number(day?.distinct_users) || 0}
                      </div>
                    </React.Fragment>
                  );
                })}

                <div className="flex items-center px-2 py-1.5 text-left font-semibold text-slate-600" dir="rtl">סה״כ לפי שעה</div>
                {Array.from({ length: 24 }, (_, hour) => (
                  <div key={`total-${hour}`} className="flex items-center justify-center py-1.5 font-semibold text-slate-600">
                    {Number(hourTotals[hour]) || 0}
                  </div>
                ))}
                <div className="flex items-center justify-center py-1.5 font-semibold text-slate-600">
                  {hourTotals.reduce((sum, value) => sum + (Number(value) || 0), 0)}
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">{peakLabel(data?.peak, heatmapDays)}</p>
          </>
        )}
      </div>
    </section>
  );
}