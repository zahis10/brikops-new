import { formatRelativeHe } from '../relativeTime';
const now = new Date('2026-09-10T12:00:00Z').getTime();
test('formats relative Hebrew time buckets', () => {
  expect(formatRelativeHe(new Date(now - 30000).toISOString(), now)).toBe('עכשיו');
  expect(formatRelativeHe(new Date(now - 60000).toISOString(), now)).toBe('לפני דקה');
  expect(formatRelativeHe(new Date(now - 120000).toISOString(), now)).toBe('לפני 2 דקות');
  expect(formatRelativeHe(new Date(now - 3600000).toISOString(), now)).toBe('לפני שעה');
  expect(formatRelativeHe(new Date(now - 7200000).toISOString(), now)).toBe('לפני 2 שעות');
  expect(formatRelativeHe(new Date(now - 86400000).toISOString(), now)).toBe('אתמול');
  expect(formatRelativeHe(new Date(now - 3 * 86400000).toISOString(), now)).toBe('לפני 3 ימים');
});