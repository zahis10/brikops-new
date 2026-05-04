import React, { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2, AlertCircle, LayoutGrid } from 'lucide-react';
import { useMatrixData } from '../hooks/useMatrixData';
import MatrixListView from '../components/matrix/MatrixListView';
import MatrixGridView from '../components/matrix/MatrixGridView';
import StatusLegend from '../components/matrix/StatusLegend';

export default function ExecutionMatrixPage() {
  const { projectId } = useParams();
  const { data, loading, error, refresh } = useMatrixData(projectId);

  // #483 returns units with floor_id but NOT floor metadata.
  // Phase 2A: synthesize minimal floorsById from units. Future
  // batch can have backend embed floors[] in the matrix response.
  const floorsById = useMemo(() => {
    const map = {};
    if (data?.floors) {
      for (const f of data.floors) map[f.id] = f;
    }
    if (data?.units) {
      for (const u of data.units) {
        if (u.floor_id && !map[u.floor_id]) {
          map[u.floor_id] = { id: u.floor_id, floor_number: u.floor_number || '?' };
        }
      }
    }
    return map;
  }, [data]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 sm:p-6" dir="rtl">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-center gap-2 text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">טוען מטריצה...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 sm:p-6" dir="rtl">
        <div className="max-w-7xl mx-auto">
          <div className="bg-white rounded-xl border border-red-200 p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-bold text-red-900">שגיאה בטעינת המטריצה</div>
                <div className="text-xs text-red-700 mt-1">{error}</div>
                <button
                  onClick={refresh}
                  className="mt-3 px-3 py-2 text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-md border border-red-200"
                >
                  נסה שוב
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const stages = data?.stages || [];
  const units = data?.units || [];
  const cells = data?.cells || [];

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-violet-100 rounded-lg">
            <LayoutGrid className="w-5 h-5 text-violet-700" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg sm:text-xl font-bold text-slate-900">מטריצת ביצוע</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {units.length} דירות • {stages.length} שלבים
            </p>
          </div>
        </div>

        <div className="mb-4">
          <StatusLegend defaultOpen={false} />
        </div>

        <div className="md:hidden">
          <MatrixListView
            units={units}
            stages={stages}
            cells={cells}
            floorsById={floorsById}
          />
        </div>
        <div className="hidden md:block">
          <MatrixGridView
            units={units}
            stages={stages}
            cells={cells}
            floorsById={floorsById}
          />
        </div>
      </div>
    </div>
  );
}
