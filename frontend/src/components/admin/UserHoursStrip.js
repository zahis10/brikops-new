import React, { useEffect, useState } from 'react';

function parseDateOnly(value) {
  if (typeof value !== 'string') return null;
  const parts = value.split('-').map(Number);
  if (parts.length !== 3 || parts.some(part => !Number.isInteger(part))) return null;
  const [year, month, day] = parts;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

// Julian day arithmetic keeps these date-only rows independent of browser time zones.
function dayNumber({ year, month, day }) {
  const a = Math.floor((14 - month) / 12);
  const y = year + 4800 - a;
  const m = month + (12 * a) - 3;
  return day + Math.floor((153 * m + 2) / 5) + (365 * y) + Math.floor(y / 4)
    - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
}

function dateFromDayNumber(value) {
  const a = value + 32044;
  const b = Math.floor((4 * a + 3) / 146097);
  const c = a - Math.floor((146097 * b) / 4);
  const d = Math.floor((4 * c + 3) / 1461);
  const e = c - Math.floor((1461 * d) / 4);
  const m = Math.floor((5 * e + 2) / 153);
  const day = e - Math.floor((153 * m + 2) / 5) + 1;
  const month = m + 3 - (12 * Math.floor(m / 10));
  const year = (100 * b) + d - 4800 + Math.floor(m / 10);
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function recentDateKeys(today) {
  const parsed = parseDateOnly(today);
  if (!parsed) return Array.from({ length: 7 }, (_, index) => `day-${index}`);
  const newest = dayNumber(parsed);
  return Array.from({ length: 7 }, (_, index) => dateFromDayNumber(newest - index));
}

function hoursForDate(hours, date) {
  const values = Array.isArray(hours?.[date]) ? hours[date] : [];
  return new Set(values.map(Number).filter(hour => Number.isInteger(hour) && hour >= 0 && hour < 24));
}

function dateLabel(date, today) {
  if (date === today) return 'היום';
  const parts = date.split('-').map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? `${parts[2]}.${parts[1]}` : '—';
}

function cellTitle(hour, active) {
  return `${String(hour).padStart(2, '0')}:00 – ${active ? 'פעיל' : 'לא פעיל'}`;
}

function HourCells({ activeHours, compact }) {
  return (
    <div
      className={`grid gap-px ${compact ? 'w-full' : 'min-w-0 flex-1'}`}
      style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))', direction: 'ltr' }}
      dir="ltr"
    >
      {Array.from({ length: 24 }, (_, hour) => {
        const active = activeHours.has(hour);
        return (
          <span
            key={hour}
            className={`min-w-[4px] rounded-sm ${compact ? 'h-3' : 'h-2.5'} ${active ? 'bg-emerald-500' : 'bg-slate-100'}`}
            title={cellTitle(hour, active)}
            aria-label={cellTitle(hour, active)}
          />
        );
      })}
    </div>
  );
}

export default function UserHoursStrip({ hours = {}, today, compact = false }) {
  const [expanded, setExpanded] = useState(!compact);
  const dates = recentDateKeys(today);

  useEffect(() => {
    setExpanded(!compact);
  }, [compact]);

  return (
    <button
      type="button"
      className="block w-full rounded-md p-1 text-left hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-300"
      onClick={() => setExpanded(value => !value)}
      aria-expanded={expanded}
      aria-label={expanded ? 'הסתרת שעות פעילות לשבעת הימים האחרונים' : 'הצגת שעות פעילות לשבעת הימים האחרונים'}
      title={expanded ? 'הסתרת שבעת הימים' : 'הצגת שבעת הימים'}
    >
      {expanded ? (
        <div className="space-y-1" dir="ltr" style={{ direction: 'ltr' }}>
          {dates.map((date, index) => (
            <div key={date} className="flex min-w-0 items-center gap-2" style={{ direction: 'ltr' }}>
              <span className="w-12 shrink-0 truncate text-left text-[10px] text-slate-500" dir="rtl">
                {dateLabel(date, today)}
              </span>
              <HourCells activeHours={hoursForDate(hours, date)} />
            </div>
          ))}
        </div>
      ) : (
        <HourCells activeHours={hoursForDate(hours, today)} compact />
      )}
    </button>
  );
}