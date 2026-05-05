import { useState, useEffect, useCallback, useRef } from 'react';
import { matrixService } from '../services/matrixService';

export function useMatrixData(projectId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const result = await matrixService.getMatrix(projectId);
      if (!controller.signal.aborted) {
        setData(result);
        setLoading(false);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err?.response?.data?.detail || 'שגיאה בטעינת המטריצה');
        setLoading(false);
      }
    }
  }, [projectId]);

  useEffect(() => {
    load();
    return () => {
      if (abortRef.current) abortRef.current.abort();
    };
  }, [load]);

  // #491 Phase 2B — optimistic cell update with revert on error.
  // Snapshots the current cells array, applies an optimistic cell
  // immediately so the UI reflects the change, then awaits the API.
  // On success, replaces the optimistic placeholder with the server
  // response so last_updated_by / last_actor_name reflect reality.
  // On error, restores the previous snapshot and surfaces the detail.
  const updateCell = useCallback(async (unitId, stageId, payload) => {
    if (!projectId || !data) return { ok: false, error: 'no_data' };
    const prevCells = data.cells || [];
    const cellKey = `${unitId}::${stageId}`;
    const existingIdx = prevCells.findIndex(
      c => `${c.unit_id}::${c.stage_id}` === cellKey
    );
    const optimisticCell = {
      unit_id: unitId,
      stage_id: stageId,
      status: payload.status ?? null,
      note: payload.note ?? null,
      text_value: payload.text_value ?? null,
      last_updated_at: new Date().toISOString(),
      last_updated_by: '__optimistic__',
      last_actor_name: 'אתה',
    };
    const optimisticCells = existingIdx >= 0
      ? prevCells.map((c, i) => (i === existingIdx ? optimisticCell : c))
      : [...prevCells, optimisticCell];
    setData(prev => (prev ? { ...prev, cells: optimisticCells } : prev));

    try {
      const result = await matrixService.updateCell(projectId, unitId, stageId, payload);
      setData(prev => {
        if (!prev) return prev;
        const cells = (prev.cells || []).map(c =>
          `${c.unit_id}::${c.stage_id}` === cellKey ? { ...c, ...result } : c
        );
        return { ...prev, cells };
      });
      return { ok: true, cell: result };
    } catch (err) {
      setData(prev => (prev ? { ...prev, cells: prevCells } : prev));
      const detail = err?.response?.data?.detail || 'שגיאה בשמירה';
      return { ok: false, error: detail };
    }
  }, [projectId, data]);

  return { data, loading, error, refresh: load, updateCell };
}
