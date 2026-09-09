export const buildSpareContext = (spareStatus = {}) => {
  const categories = spareStatus.categories || [];
  return {
    short: categories.filter(row => row.status === 'short').map(row => ({
      name: row.name,
      missing: row.missing || 0,
      measure: row.measure,
      zero: Boolean(row.entered && row.actual === 0),
    })),
    borderline: categories.filter(row => row.status === 'borderline').map(row => row.name),
  };
};

export const contextLine = (context = {}) => {
  const short = (context.short || []).map(({ name, missing, zero }) =>
    missing > 0 ? `${name} ${missing}` : zero ? `${name} (אין ספייר)` : name
  );
  const borderline = context.borderline || [];
  return [short.length && `חסר: ${short.join(', ')}`, borderline.length && `גבולי: ${borderline.join(', ')}`].filter(Boolean).join(' · ');
};

export const defaultText = (urgency, unitLabel, context) => urgency === 'urgent'
  ? `דחוף להזמין ריצוף ספייר לדירה ${unitLabel} — חסר ${context.short.length === 1 ? 'סוג אחד' : `${context.short.length} סוגים`}`
  : `להשלים ריצוף ספייר לדירה ${unitLabel} — ${contextLine(context)}`;

export const canEscalate = (spareStatus = {}) => ['short', 'borderline'].includes(spareStatus.overall);