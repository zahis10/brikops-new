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

  return { data, loading, error, refresh: load };
}
