import { useState, useMemo, useCallback } from 'react';

/**
 * Phase 2D-1 (#500) — Excel-style filter state for the Execution Matrix.
 *
 * Filter logic per Zahi 2026-05-05: "טבלת אקסל משופרת".
 *   - AND between sections (different columns)
 *   - OR within a section (multiple values for the same column)
 *
 * Empty-value sentinel: '__empty__' is the FRONTEND-only marker for the
 * "(ריק)" checkbox. Converted to "" before sending to backend (PART 6),
 * and "" coming from a saved view is converted back to '__empty__' so
 * checkbox lookups stay clean (array.includes() never sees null/undefined).
 *
 * Pure helpers below are exported so they can be unit-tested without
 * React's renderHook (which would require @testing-library/react — not
 * installed in this repo).
 */

const EMPTY = '__empty__';

// ===== Pure helpers (exported for tests) =====

export const initialFilters = () => ({
  building_ids: [],
  apartment_search: '',
  search_text: '',
  stage_status_filters: {},   // { [stageId]: string[] }
  tag_value_filters: {},      // { [stageId]: string[] }
});

/** Toggle a value in an array (immutable). */
export function toggleInArray(arr, value) {
  if (!Array.isArray(arr)) return [value];
  return arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value];
}

/** Toggle a value inside `dict[key]` (creates the array if missing). */
export function toggleInDict(dict, key, value) {
  const next = { ...(dict || {}) };
  next[key] = toggleInArray(next[key] || [], value);
  if (next[key].length === 0) delete next[key];
  return next;
}

/** Excel-pattern filtering: AND across, OR within. */
export function computeFilteredUnits(units, cellsByUnitStage, stages, filters) {
  if (!Array.isArray(units)) return [];
  const f = filters || initialFilters();
  const stageList = Array.isArray(stages) ? stages : [];
  const cells = cellsByUnitStage || {};

  return units.filter(u => {
    // 1. Building (OR within, AND with rest)
    if (f.building_ids?.length > 0 && !f.building_ids.includes(u.building_id)) {
      return false;
    }

    // 2. Apartment search (substring on unit_no)
    if (f.apartment_search) {
      const q = String(f.apartment_search).toLowerCase();
      if (!String(u.unit_no ?? '').toLowerCase().includes(q)) return false;
    }

    // 3. Per-stage status filters
    for (const [stageId, allowed] of Object.entries(f.stage_status_filters || {})) {
      if (!allowed?.length) continue;
      const cell = cells[`${u.id}::${stageId}`];
      const status = cell?.status ?? EMPTY;
      if (!allowed.includes(status)) return false;
    }

    // 4. Per-tag value filters
    for (const [stageId, allowed] of Object.entries(f.tag_value_filters || {})) {
      if (!allowed?.length) continue;
      const cell = cells[`${u.id}::${stageId}`];
      const raw = cell?.text_value;
      const value = (raw == null || raw === '') ? EMPTY : raw;
      if (!allowed.includes(value)) return false;
    }

    // 5. Global free-text search across unit_no + cell text + cell note
    if (f.search_text) {
      const q = String(f.search_text).toLowerCase();
      const inUnitNo = String(u.unit_no ?? '').toLowerCase().includes(q);
      const inCells = stageList.some(s => {
        const c = cells[`${u.id}::${s.id}`];
        return (
          String(c?.text_value ?? '').toLowerCase().includes(q) ||
          String(c?.note ?? '').toLowerCase().includes(q)
        );
      });
      if (!inUnitNo && !inCells) return false;
    }

    return true;
  });
}

/** Active count per section + total. */
export function computeActiveCount(filters) {
  const f = filters || initialFilters();
  const stage_status = {};
  let stageStatusTotal = 0;
  for (const [k, v] of Object.entries(f.stage_status_filters || {})) {
    if (v?.length) { stage_status[k] = v.length; stageStatusTotal += v.length; }
  }
  const tag_value = {};
  let tagValueTotal = 0;
  for (const [k, v] of Object.entries(f.tag_value_filters || {})) {
    if (v?.length) { tag_value[k] = v.length; tagValueTotal += v.length; }
  }
  const building = f.building_ids?.length || 0;
  const apartment = f.apartment_search ? 1 : 0;
  const search = f.search_text ? 1 : 0;
  return {
    total: building + apartment + search + stageStatusTotal + tagValueTotal,
    building, apartment, search,
    stage_status, tag_value,
  };
}

/** Distinct text_value across cells of one stage (for tag-section checkboxes). */
export function distinctTagValuesFor(stageId, cellsByUnitStage) {
  const set = new Set();
  let hasEmpty = false;
  for (const [key, cell] of Object.entries(cellsByUnitStage || {})) {
    if (!key.endsWith(`::${stageId}`)) continue;
    const v = cell?.text_value;
    if (v == null || v === '') hasEmpty = true;
    else set.add(v);
  }
  const out = Array.from(set).sort((a, b) => String(a).localeCompare(String(b), 'he'));
  if (hasEmpty) out.push(EMPTY);
  return out;
}

/** Convert frontend filter state → backend payload (sentinel → ""). */
export function serializeFilters(filters) {
  const f = filters || initialFilters();
  const mapDict = (dict) => {
    const out = {};
    for (const [k, v] of Object.entries(dict || {})) {
      if (!Array.isArray(v) || v.length === 0) continue;
      out[k] = v.map(x => (x === EMPTY ? '' : x));
    }
    return out;
  };
  return {
    building_ids: f.building_ids?.length ? [...f.building_ids] : [],
    stage_status_filters: mapDict(f.stage_status_filters),
    tag_value_filters: mapDict(f.tag_value_filters),
    search_text: f.search_text || '',
    // apartment_search is frontend-only (pure substring); not in backend schema.
  };
}

/** Convert backend payload → frontend filter state ("" → sentinel). */
export function deserializeFilters(payload) {
  const p = payload || {};
  const mapDict = (dict) => {
    const out = {};
    for (const [k, v] of Object.entries(dict || {})) {
      if (!Array.isArray(v) || v.length === 0) continue;
      out[k] = v.map(x => (x === '' || x == null ? EMPTY : x));
    }
    return out;
  };
  return {
    building_ids: Array.isArray(p.building_ids) ? [...p.building_ids] : [],
    apartment_search: '', // backend doesn't store this — Phase 2D-1 keeps client-side
    search_text: p.search_text || '',
    stage_status_filters: mapDict(p.stage_status_filters),
    tag_value_filters: mapDict(p.tag_value_filters),
  };
}

// ===== Hook =====

export default function useMatrixFilters({ units, cellsByUnitStage, stages }) {
  const [filters, setFilters] = useState(initialFilters);

  const filteredUnits = useMemo(
    () => computeFilteredUnits(units || [], cellsByUnitStage || {}, stages || [], filters),
    [units, cellsByUnitStage, stages, filters]
  );

  const activeCount = useMemo(() => computeActiveCount(filters), [filters]);

  const toggleBuilding = useCallback((buildingId) => {
    setFilters(prev => ({ ...prev, building_ids: toggleInArray(prev.building_ids, buildingId) }));
  }, []);

  const toggleStageStatus = useCallback((stageId, statusValue) => {
    setFilters(prev => ({
      ...prev,
      stage_status_filters: toggleInDict(prev.stage_status_filters, stageId, statusValue),
    }));
  }, []);

  const toggleTagValue = useCallback((stageId, value) => {
    setFilters(prev => ({
      ...prev,
      tag_value_filters: toggleInDict(prev.tag_value_filters, stageId, value),
    }));
  }, []);

  const setApartmentSearch = useCallback((v) => {
    setFilters(prev => ({ ...prev, apartment_search: v || '' }));
  }, []);

  const setSearchText = useCallback((v) => {
    setFilters(prev => ({ ...prev, search_text: v || '' }));
  }, []);

  const reset = useCallback(() => setFilters(initialFilters()), []);

  const loadSavedView = useCallback((view) => {
    setFilters(deserializeFilters(view?.filters));
  }, []);

  const distinctTagValues = useCallback(
    (stageId) => distinctTagValuesFor(stageId, cellsByUnitStage || {}),
    [cellsByUnitStage]
  );

  const currentFilterPayload = useMemo(() => serializeFilters(filters), [filters]);

  return {
    filters, filteredUnits, activeCount,
    toggleBuilding, toggleStageStatus, toggleTagValue,
    setApartmentSearch, setSearchText,
    reset, loadSavedView,
    currentFilterPayload, distinctTagValues,
  };
}
