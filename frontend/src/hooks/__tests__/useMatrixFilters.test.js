import {
  computeFilteredUnits,
  computeActiveCount,
  serializeFilters,
  deserializeFilters,
  initialFilters,
  toggleInArray,
  toggleInDict,
  spareStatusMatches,
} from '../useMatrixFilters';

const mkCells = (entries) => {
  const map = {};
  for (const [unitId, stageId, props] of entries) {
    map[`${unitId}::${stageId}`] = { unit_id: unitId, stage_id: stageId, ...props };
  }
  return map;
};

const units = [
  { id: 'u1', unit_no: '101', building_id: 'A' },
  { id: 'u2', unit_no: '102', building_id: 'A' },
  { id: 'u3', unit_no: '201', building_id: 'B' },
  { id: 'u4', unit_no: '202', building_id: 'B' },
];

const stages = [
  { id: 's_plaster', title: 'טיח', type: 'status' },
  { id: 's_sale', title: 'סוג מכירה', type: 'tag' },
];

describe('useMatrixFilters pure helpers', () => {
  test('T1 — building + tag AND combination filters correctly', () => {
    const cells = mkCells([
      ['u1', 's_sale', { text_value: 'שוק חופשי' }],
      ['u2', 's_sale', { text_value: 'משתכן' }],
      ['u3', 's_sale', { text_value: 'שוק חופשי' }],
    ]);
    const filters = {
      ...initialFilters(),
      building_ids: ['A'],
      tag_value_filters: { s_sale: ['שוק חופשי'] },
    };
    const out = computeFilteredUnits(units, cells, stages, filters);
    expect(out.map(u => u.id)).toEqual(['u1']); // A AND שוק חופשי
  });

  test('T2 — status filter OR within: multiple statuses keep unit if ANY match', () => {
    const cells = mkCells([
      ['u1', 's_plaster', { status: 'completed' }],
      ['u2', 's_plaster', { status: 'partial' }],
      ['u3', 's_plaster', { status: 'not_done' }],
      ['u4', 's_plaster', { status: 'in_progress' }],
    ]);
    const filters = {
      ...initialFilters(),
      stage_status_filters: { s_plaster: ['completed', 'partial'] },
    };
    const out = computeFilteredUnits(units, cells, stages, filters);
    expect(out.map(u => u.id).sort()).toEqual(['u1', 'u2']);
  });

  test('T3 — global search_text matches in cell.text_value AND cell.note', () => {
    const cells = mkCells([
      ['u1', 's_sale', { text_value: 'מיוחד' }],
      ['u2', 's_plaster', { note: 'הערה מיוחדת' }],
      ['u3', 's_sale', { text_value: 'רגיל' }],
    ]);
    const filters = { ...initialFilters(), search_text: 'מיוחד' };
    const out = computeFilteredUnits(units, cells, stages, filters);
    expect(out.map(u => u.id).sort()).toEqual(['u1', 'u2']);
  });

  test('T4 — activeCount counts every active section correctly', () => {
    const filters = {
      building_ids: ['A', 'B'],
      apartment_search: '10',
      search_text: 'foo',
      stage_status_filters: { s_plaster: ['completed', 'partial'] },
      tag_value_filters: { s_sale: ['שוק חופשי'] },
    };
    const c = computeActiveCount(filters);
    expect(c.building).toBe(2);
    expect(c.apartment).toBe(1);
    expect(c.search).toBe(1);
    expect(c.stage_status).toEqual({ s_plaster: 2 });
    expect(c.tag_value).toEqual({ s_sale: 1 });
    expect(c.total).toBe(2 + 1 + 1 + 2 + 1); // 7
  });

  test('T5 — loadSavedView replaces state atomically (no leak between switches)', () => {
    // Apply view A
    const viewA = {
      building_ids: ['A'],
      stage_status_filters: { s_plaster: ['completed'] },
      tag_value_filters: {},
      search_text: '',
    };
    const stateA = deserializeFilters(viewA);
    expect(stateA.building_ids).toEqual(['A']);
    expect(stateA.stage_status_filters).toEqual({ s_plaster: ['completed'] });

    // Switch to view B — must not leak A's stage filter
    const viewB = {
      building_ids: ['B'],
      tag_value_filters: { s_sale: ['משתכן'] },
    };
    const stateB = deserializeFilters(viewB);
    expect(stateB.building_ids).toEqual(['B']);
    expect(stateB.stage_status_filters).toEqual({}); // CLEARED, not merged
    expect(stateB.tag_value_filters).toEqual({ s_sale: ['משתכן'] });
    expect(stateB.search_text).toBe('');
  });

  test('T6 — sentinel boundary: __empty__ ↔ "" round-trips correctly', () => {
    // Frontend toggles "(ריק)" — internal state has '__empty__'
    let frontendState = { ...initialFilters() };
    frontendState.stage_status_filters = toggleInDict(
      frontendState.stage_status_filters, 's_plaster', '__empty__'
    );
    expect(frontendState.stage_status_filters.s_plaster).toEqual(['__empty__']);

    // Serialize for backend → '__empty__' becomes ""
    const payload = serializeFilters(frontendState);
    expect(payload.stage_status_filters.s_plaster).toEqual(['']);

    // Round-trip: load back from backend → "" becomes '__empty__' again
    const restored = deserializeFilters(payload);
    expect(restored.stage_status_filters.s_plaster).toEqual(['__empty__']);

    // Same for tag values
    const tagState = {
      ...initialFilters(),
      tag_value_filters: { s_sale: ['__empty__', 'שוק חופשי'] },
    };
    const tagPayload = serializeFilters(tagState);
    expect(tagPayload.tag_value_filters.s_sale).toEqual(['', 'שוק חופשי']);
    const tagRestored = deserializeFilters(tagPayload);
    expect(tagRestored.tag_value_filters.s_sale).toEqual(['__empty__', 'שוק חופשי']);
  });

  test('T7 — reset semantics: applying ≥4 sections then resetting → all empty + activeCount.total===0', () => {
    let f = initialFilters();
    f.building_ids = toggleInArray(f.building_ids, 'A');
    f.apartment_search = '10';
    f.stage_status_filters = toggleInDict(f.stage_status_filters, 's_plaster', 'completed');
    f.tag_value_filters = toggleInDict(f.tag_value_filters, 's_sale', 'שוק חופשי');
    expect(computeActiveCount(f).total).toBe(4);

    // Simulate reset() — useMatrixFilters calls setFilters(initialFilters())
    const reset = initialFilters();
    expect(reset.building_ids).toEqual([]);
    expect(reset.apartment_search).toBe('');
    expect(reset.search_text).toBe('');
    expect(reset.stage_status_filters).toEqual({});
    expect(reset.tag_value_filters).toEqual({});
    expect(computeActiveCount(reset).total).toBe(0);
  });

  test('T8 — spare status filters short and defaults missing summaries to no_profile', () => {
    const spareByUnit = {
      u1: { overall: 'short' },
      u2: { overall: 'ok' },
      u3: { overall: 'short' },
    };
    const shortFilters = { ...initialFilters(), spare_status: ['short'] };
    expect(
      computeFilteredUnits(units, {}, stages, shortFilters, spareByUnit).map(u => u.id)
    ).toEqual(['u1', 'u3']);

    const noProfileFilters = { ...initialFilters(), spare_status: ['no_profile'] };
    expect(
      computeFilteredUnits(units, {}, stages, noProfileFilters, spareByUnit).map(u => u.id)
    ).toEqual(['u4']);
  });

  test('T9 — activeCount includes each selected spare status', () => {
    const filters = {
      ...initialFilters(),
      building_ids: ['A'],
      spare_status: ['short', 'not_entered'],
    };
    const count = computeActiveCount(filters);
    expect(count.spare).toBe(2);
    expect(count.total).toBe(3);
  });

  test('T10 — spare_status survives saved-view serialization round-trip', () => {
    const filters = {
      ...initialFilters(),
      spare_status: ['short', 'borderline'],
    };
    const payload = serializeFilters(filters);
    expect(payload.spare_status).toEqual(['short', 'borderline']);
    expect(deserializeFilters(payload).spare_status).toEqual(['short', 'borderline']);
    expect(deserializeFilters({}).spare_status).toEqual([]);
  });

  test('T11 — old four-argument helper calls retain existing results', () => {
    const cells = mkCells([
      ['u1', 's_sale', { text_value: 'שוק חופשי' }],
      ['u2', 's_sale', { text_value: 'משתכן' }],
    ]);
    const filters = {
      ...initialFilters(),
      building_ids: ['A'],
      tag_value_filters: { s_sale: ['שוק חופשי'] },
    };
    expect(computeFilteredUnits(units, cells, stages, filters).map(u => u.id)).toEqual(['u1']);
  });

  test('T12 — spare problem statuses match any category while non-problem statuses use overall', () => {
    const extendedUnits = [
      ...units,
      { id: 'u5', unit_no: '301', building_id: 'C' },
      { id: 'u6', unit_no: '302', building_id: 'C' },
      { id: 'u7', unit_no: '303', building_id: 'C' },
      { id: 'u8', unit_no: '304', building_id: 'C' },
      { id: 'u9', unit_no: '305', building_id: 'C' },
    ];
    const spareByUnit = {
      u1: {
        overall: 'short',
        short: [{ name: 'a', missing: 1, measure: 'tiles' }],
        borderline: ['b'],
      },
      u2: { overall: 'borderline', borderline: ['b'] },
      u3: { overall: 'not_entered', not_entered: ['n'], borderline: ['b'] },
      u4: { overall: 'ok' },
      u5: {
        overall: 'recorded',
        recorded: ['a', 'b'],
        unfilled: ['c'],
        categories_total: 3,
      },
      u6: { overall: 'no_target', unfilled: ['a'] },
      u7: { overall: 'ok', unfilled: [] },
      u8: { overall: 'no_target' },
      u9: {
        overall: 'no_profile',
        unfilled: ['a'],
        entered_count: 1,
        applicable_count: 5,
      },
    };
    const idsFor = (spareStatus) => computeFilteredUnits(
      extendedUnits,
      {},
      stages,
      { ...initialFilters(), spare_status: spareStatus },
      spareByUnit
    ).map(unit => unit.id);

    expect(idsFor(['borderline'])).toEqual(['u1', 'u2', 'u3']);
    expect(idsFor(['short'])).toEqual(['u1']);
    expect(idsFor(['not_entered'])).toEqual(['u3', 'u5', 'u6', 'u8', 'u9']);
    expect(idsFor(['ok'])).toEqual(['u4', 'u7']);
    expect(idsFor(['recorded'])).toEqual(['u5']);
    expect(idsFor(['no_target'])).toEqual(['u6', 'u8']);
    expect(idsFor(['short', 'ok'])).toEqual(['u1', 'u4', 'u7']);
    expect(idsFor(['no_profile'])).toEqual(['u9']);
    expect(spareStatusMatches(spareByUnit.u5, 'not_entered')).toBe(true);
    expect(spareStatusMatches(spareByUnit.u5, 'ok')).toBe(false);
    expect(spareStatusMatches(spareByUnit.u6, 'recorded')).toBe(false);
    expect(spareStatusMatches(spareByUnit.u7, 'not_entered')).toBe(false);
    expect(spareStatusMatches(spareByUnit.u8, 'not_entered')).toBe(true);
    expect(spareStatusMatches(spareByUnit.u8, 'no_target')).toBe(true);
    expect(spareStatusMatches(spareByUnit.u9, 'not_entered')).toBe(true);
    expect(spareStatusMatches(spareByUnit.u9, 'no_profile')).toBe(true);
    expect(spareStatusMatches(undefined, 'no_profile')).toBe(true);
  });
});
