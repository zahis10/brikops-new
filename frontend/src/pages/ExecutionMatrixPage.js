import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, LayoutGrid, ArrowRight, Settings, Download } from 'lucide-react';
import { downloadBlob } from '../utils/fileDownload';
import { toast } from 'sonner';
import { useMatrixData } from '../hooks/useMatrixData';
import useMatrixFilters from '../hooks/useMatrixFilters';
import { matrixService } from '../services/matrixService';
import MatrixListView from '../components/matrix/MatrixListView';
import MatrixGridView from '../components/matrix/MatrixGridView';
import StatusLegend from '../components/matrix/StatusLegend';
import CellEditDialog from '../components/matrix/CellEditDialog';
import StageManagementDialog from '../components/matrix/StageManagementDialog';
import MatrixFilterFAB from '../components/matrix/MatrixFilterFAB';
import MatrixFilterDrawer from '../components/matrix/MatrixFilterDrawer';

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

  // #500 Phase 2D-1 — filter state + saved views. MUST come before any early
  // return so React hook order stays stable across renders.
  const stages = useMemo(() => data?.stages || [], [data]);
  const units = useMemo(() => data?.units || [], [data]);
  const cells = useMemo(() => data?.cells || [], [data]);

  const cellsByUnitStage = useMemo(() => {
    const map = {};
    for (const c of cells) map[`${c.unit_id}::${c.stage_id}`] = c;
    return map;
  }, [cells]);

  const filterAPI = useMatrixFilters({ units, cellsByUnitStage, stages });
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [savedViews, setSavedViews] = useState([]);

  // #502 — Excel export state
  const [exporting, setExporting] = useState(false);

  const handleExport = useCallback(async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const { blob, filename } = await matrixService.exportXlsx(projectId, {
        unit_ids: filterAPI.filteredUnits.map(u => u.id),
        stage_ids: stages.map(s => s.id),
      });
      await downloadBlob(
        blob,
        filename,
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      );
    } catch (e) {
      // responseType:'blob' prevents axios from auto-parsing JSON errors —
      // read the blob as text and try to surface the backend `detail`
      // (e.g. the 2000-unit cap message in Hebrew).
      let msg = 'ייצוא נכשל. נסה שוב.';
      if (e?.response?.data instanceof Blob) {
        try {
          const text = await e.response.data.text();
          const json = JSON.parse(text);
          if (json?.detail) msg = json.detail;
        } catch { /* keep generic message */ }
      }
      alert(msg);
    } finally {
      setExporting(false);
    }
  }, [exporting, projectId, filterAPI.filteredUnits, stages]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    matrixService.listSavedViews(projectId)
      .then(views => { if (!cancelled) setSavedViews(views); })
      .catch(() => { /* non-fatal — pills just won't show */ });
    return () => { cancelled = true; };
  }, [projectId]);

  const handleSaveCurrentView = useCallback(async (title) => {
    try {
      const created = await matrixService.createSavedView(projectId, {
        title, filters: filterAPI.currentFilterPayload,
      });
      setSavedViews(prev => [...prev, created]);
      toast.success('התצוגה נשמרה');
      return { ok: true };
    } catch (err) {
      const msg = err?.response?.data?.detail || 'שגיאה בשמירת התצוגה';
      return { ok: false, error: msg };
    }
  }, [projectId, filterAPI.currentFilterPayload]);

  const handleDeleteSavedView = useCallback(async (viewId) => {
    const prev = savedViews;
    setSavedViews(p => p.filter(v => v.id !== viewId));
    try {
      await matrixService.deleteSavedView(projectId, viewId);
    } catch (err) {
      setSavedViews(prev);
      toast.error('שגיאה במחיקת התצוגה');
    }
  }, [projectId, savedViews]);

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
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="p-2 rounded-lg hover:bg-slate-100 active:bg-slate-200 transition-colors disabled:opacity-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="ייצוא לExcel"
            title="ייצוא לExcel"
          >
            {exporting
              ? <Loader2 className="w-5 h-5 text-slate-600 animate-spin" />
              : <Download className="w-5 h-5 text-slate-600" />}
          </button>
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
            units={filterAPI.filteredUnits}
            stages={stages}
            cells={cells}
            floorsById={floorsById}
            buildingsById={buildingsById}
            onCellClick={handleCellClick}
          />
        </div>
        <div className="hidden md:block">
          <MatrixGridView
            units={filterAPI.filteredUnits}
            stages={stages}
            cells={cells}
            floorsById={floorsById}
            buildingsById={buildingsById}
            onCellClick={handleCellClick}
          />
        </div>
      </div>

      <MatrixFilterFAB
        activeCount={filterAPI.activeCount.total}
        onClick={() => setFiltersOpen(true)}
      />

      <MatrixFilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        filters={filterAPI.filters}
        filteredCount={filterAPI.filteredUnits.length}
        activeCount={filterAPI.activeCount}
        toggleBuilding={filterAPI.toggleBuilding}
        toggleStageStatus={filterAPI.toggleStageStatus}
        toggleTagValue={filterAPI.toggleTagValue}
        setApartmentSearch={filterAPI.setApartmentSearch}
        setSearchText={filterAPI.setSearchText}
        reset={filterAPI.reset}
        loadSavedView={filterAPI.loadSavedView}
        distinctTagValues={filterAPI.distinctTagValues}
        buildings={data?.buildings || []}
        stages={stages}
        savedViews={savedViews}
        onSaveCurrentView={handleSaveCurrentView}
        onDeleteSavedView={handleDeleteSavedView}
      />

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
        initialAllBaseStages={data?.template_stages || []}
      />
    </div>
  );
}
