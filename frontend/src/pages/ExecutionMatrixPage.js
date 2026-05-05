import React, { useMemo, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, LayoutGrid, ArrowRight, Settings } from 'lucide-react';
import { useMatrixData } from '../hooks/useMatrixData';
import MatrixListView from '../components/matrix/MatrixListView';
import MatrixGridView from '../components/matrix/MatrixGridView';
import StatusLegend from '../components/matrix/StatusLegend';
import CellEditDialog from '../components/matrix/CellEditDialog';
import StageManagementDialog from '../components/matrix/StageManagementDialog';

export default function ExecutionMatrixPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh, updateCell, updateStages } = useMatrixData(projectId);

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

  // #485 — building count for header subtitle
  const buildingCount = useMemo(() => {
    if (!data?.units) return 0;
    return new Set(
      data.units.map(u => u.building_id).filter(Boolean)
    ).size;
  }, [data]);

  // #486 — buildingsById map for separate sticky column in views
  const buildingsById = useMemo(() => {
    const map = {};
    if (data?.buildings) {
      for (const b of data.buildings) map[b.id] = b;
    }
    return map;
  }, [data]);

  // #491 Phase 2B — cell edit dialog state.
  const [editing, setEditing] = useState(null); // { unit, stage, cell } | null
  const canEdit = data?.permissions?.can_edit ?? false;

  // #495 Phase 2C — stage management dialog state.
  const [stageManageOpen, setStageManageOpen] = useState(false);

  const handleCellClick = useCallback((unit, stage, cell) => {
    setEditing({ unit, stage, cell });
  }, []);

  const handleSaveCell = useCallback(async (payload) => {
    if (!editing) return { ok: false, error: 'no_editing' };
    return updateCell(editing.unit.id, editing.stage.id, payload);
  }, [editing, updateCell]);

  const handleSaveStages = useCallback(async (payload) => {
    return updateStages(payload);
  }, [updateStages]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-4 sm:p-6" dir="rtl">
        <div className="max-w-7xl mx-auto">
          <button
            onClick={() => navigate(`/projects/${projectId}/qc`)}
            className="p-2 hover:bg-slate-100 active:bg-slate-200 rounded-lg transition-colors mb-3 inline-flex"
            aria-label="חזרה לבקרת ביצוע"
          >
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
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
          <button
            onClick={() => navigate(`/projects/${projectId}/qc`)}
            className="p-2 hover:bg-slate-100 active:bg-slate-200 rounded-lg transition-colors mb-3 inline-flex"
            aria-label="חזרה לבקרת ביצוע"
          >
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
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
          <button
            onClick={() => navigate(`/projects/${projectId}/qc`)}
            className="p-2 hover:bg-slate-100 active:bg-slate-200 rounded-lg transition-colors"
            aria-label="חזרה לבקרת ביצוע"
          >
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
          <div className="p-2 bg-violet-100 rounded-lg">
            <LayoutGrid className="w-5 h-5 text-violet-700" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg sm:text-xl font-bold text-slate-900">מטריצת ביצוע</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {buildingCount > 0 && `${buildingCount} מבנים • `}
              {units.length} דירות • {stages.length} שלבים
            </p>
          </div>
          {canEdit && (
            <button
              onClick={() => setStageManageOpen(true)}
              className="p-2 hover:bg-slate-100 active:bg-slate-200 rounded-lg transition-colors"
              aria-label="ניהול עמודות"
              title="ניהול עמודות"
            >
              <Settings className="w-5 h-5 text-slate-600" />
            </button>
          )}
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
            buildingsById={buildingsById}
            onCellClick={handleCellClick}
          />
        </div>
        <div className="hidden md:block">
          <MatrixGridView
            units={units}
            stages={stages}
            cells={cells}
            floorsById={floorsById}
            buildingsById={buildingsById}
            onCellClick={handleCellClick}
          />
        </div>
      </div>

      <CellEditDialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        onSave={handleSaveCell}
        projectId={projectId}
        unit={editing?.unit}
        stage={editing?.stage}
        cell={editing?.cell}
        building={editing ? buildingsById[editing.unit.building_id] : null}
        floor={editing ? floorsById[editing.unit.floor_id] : null}
        canEdit={canEdit}
      />

      <StageManagementDialog
        open={stageManageOpen}
        onClose={() => setStageManageOpen(false)}
        onSave={handleSaveStages}
        stages={stages}
        initialBaseRemoved={data?.base_stages_removed || []}
      />
    </div>
  );
}
