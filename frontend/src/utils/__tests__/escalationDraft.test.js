import { buildSpareContext, canEscalate, contextLine, defaultText } from '../escalationDraft';
const context = { short: [{ name: 'א', missing: 2, measure: 'tiles', zero: false }, { name: 'ב', missing: 0, measure: 'tiles', zero: true }], borderline: ['ג'] };
test('builds escalation context and normative copy', () => {
  expect(buildSpareContext({ categories: [{ name: 'א', status: 'short', missing: 2, measure: 'tiles', entered: true, actual: 1 }, { name: 'ג', status: 'borderline' }] })).toEqual({ short: [{ name: 'א', missing: 2, measure: 'tiles', zero: false }], borderline: ['ג'] });
  expect(contextLine(context)).toBe('חסר: א 2, ב (אין ספייר) · גבולי: ג');
  expect(defaultText('urgent', '12', { ...context, short: [context.short[0]] })).toBe('דחוף להזמין ריצוף ספייר לדירה 12 — חסר סוג אחד');
  expect(defaultText('normal', '12', context)).toBe('להשלים ריצוף ספייר לדירה 12 — חסר: א 2, ב (אין ספייר) · גבולי: ג');
  expect(canEscalate({ overall: 'short' })).toBe(true); expect(canEscalate({ overall: 'ok' })).toBe(false);
});