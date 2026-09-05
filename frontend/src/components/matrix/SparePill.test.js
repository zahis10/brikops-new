import { spareSummaryText } from './SparePill';

const summary = (overall, entered_count, applicable_count, short = 0, borderline = 0) => ({
  overall,
  entered_count,
  applicable_count,
  short: Array.from({ length: short }, (_, index) => ({ name: `חסר ${index}` })),
  borderline: Array.from({ length: borderline }, (_, index) => `גבולי ${index}`),
});

describe('spareSummaryText', () => {
  test.each([
    [summary('not_entered', 1, 5), 'הוזן 1/5'],
    [summary('short', 3, 5, 1), 'חסר 1 · הוזן 3/5'],
    [summary('borderline', 4, 5, 0, 1), 'גבולי 1 · הוזן 4/5'],
    [summary('short', 5, 5, 2, 1), 'חסר 2 · גבולי 1'],
    [summary('ok', 5, 5), 'מספיק'],
    [summary('not_entered', 0, 5), 'לא הוזן'],
    [summary('not_entered', 4, 5), 'הוזן 4/5'],
    [summary('recorded', 5, 5), 'הוזן 5/5'],
    [summary('no_profile', 0, 5), 'אחר'],
    [summary('no_profile', 1, 5), 'אחר · הוזן 1/5'],
    [summary('no_profile', 5, 5), 'אחר · הוזן 5/5'],
    [summary('short', 3, 5, 2, 1), 'חסר 2 · גבולי 1 · הוזן 3/5'],
  ])('formats %# using the shared outside-label rule', (input, expected) => {
    expect(spareSummaryText(input)).toBe(expected);
  });

  test('old summary shapes remain safe', () => {
    expect(spareSummaryText({ overall: 'not_entered' })).toBe('לא הוזן');
    expect(spareSummaryText({ overall: 'no_profile' })).toBe('אחר');
  });
});
