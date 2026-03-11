import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, buildingService } from '../services/api';
import { formatUnitLabel } from '../utils/formatters';
import { Card } from '../components/ui/card';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, Building2, Layers, Home,
  ChevronDown, ChevronRight, AlertTriangle, WifiOff
} from 'lucide-react';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

const TABS = [
  { id: 'units', label: 'דירות/קומות' },
  { id: 'defects', label: 'ליקויים' },
  { id: 'qc', label: 'בקרת ביצוע' },
];

const InnerBuildingPage = () => {
  const { projectId, buildingId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(null);
  const [projectName, setProjectName] = useState('');
  const [defectData, setDefectData] = useState(null);
  const [expandedFloors, setExpandedFloors] = useState({});
  const [activeTab, setActiveTab] = useState('units');
  const [loadError, setLoadError] = useState(null);

  const handleBack = useCallback(() => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate(`/projects/${projectId}/control?tab=structure`);
    }
  }, [navigate, projectId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [hierarchyData, defectsData] = await Promise.allSettled([
        projectService.getHierarchy(projectId),
        buildingService.defectsSummary(buildingId),
      ]);

      if (hierarchyData.status === 'rejected') {
        const status = hierarchyData.reason?.response?.status;
        if (status === 403 || status === 401) {
          toast.error('אין לך הרשאה לצפות בפרויקט זה');
          navigate(`/projects`, { replace: true });
          return;
        }
        setLoadError('network');
        return;
      }

      const raw = hierarchyData.value;
      const pName = raw?.project_name || '';
      setProjectName(pName);
      const buildings = normalizeList(raw);
      const found = buildings.find(b => b.id === buildingId);
      setBuilding(found || null);

      if (defectsData.status === 'fulfilled') {
        setDefectData(defectsData.value);
      }
    } catch {
      setLoadError('network');
    } finally {
      setLoading(false);
    }
  }, [projectId, buildingId, navigate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const unitDefectMap = useMemo(() => {
    const map = {};
    if (!defectData?.floors) return map;
    for (const floor of defectData.floors) {
      for (const unit of (floor.units || [])) {
        const counts = unit.defect_counts || {};
        map[unit.id] = {
          open: (counts.open || 0) + (counts.in_progress || 0),
          total: counts.total || 0,
        };
      }
    }
    return map;
  }, [defectData]);

  const floorDefectMap = useMemo(() => {
    const map = {};
    if (!defectData?.floors) return map;
    for (const floor of defectData.floors) {
      let open = 0;
      for (const unit of (floor.units || [])) {
        const counts = unit.defect_counts || {};
        open += (counts.open || 0) + (counts.in_progress || 0);
      }
      map[floor.id] = open;
    }
    return map;
  }, [defectData]);

  const kpis = useMemo(() => {
    if (!building) return { floors: 0, units: 0, openDefects: 0 };
    const floors = (building.floors || []).length;
    const units = (building.floors || []).reduce((sum, f) => sum + (f.units || []).length, 0);
    let openDefects = 0;
    Object.values(unitDefectMap).forEach(d => { openDefects += d.open; });
    return { floors, units, openDefects };
  }, [building, unitDefectMap]);

  const handleTabClick = (tabId) => {
    if (tabId === 'defects') {
      navigate(`/projects/${projectId}/buildings/${buildingId}/defects`);
      return;
    }
    if (tabId === 'qc') {
      navigate(`/projects/${projectId}/qc`);
      return;
    }
    setActiveTab(tabId);
  };

  const toggleFloor = (floorId) => {
    setExpandedFloors(prev => ({ ...prev, [floorId]: !prev[floorId] }));
  };

  if (loading) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500 mx-auto" />
          <p className="text-sm text-slate-500 mt-3">טוען בניין...</p>
        </div>
      </div>
    );
  }

  if (loadError === 'network') {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <WifiOff className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-lg font-medium text-slate-600 mb-1">שגיאת תקשורת</p>
          <p className="text-sm text-slate-400 mb-4">לא ניתן לטעון את נתוני הבניין</p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={loadData}
              className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors"
            >
              נסה שוב
            </button>
            <button
              onClick={handleBack}
              className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-300 transition-colors"
            >
              חזרה
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!building) {
    return (
      <div dir="rtl" className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Building2 className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-lg font-medium text-slate-600 mb-1">בניין לא נמצא</p>
          <p className="text-sm text-slate-400 mb-4">ייתכן שהבניין הוסר או שהקישור שגוי</p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition-colors"
          >
            חזרה לפרויקט
          </button>
        </div>
      </div>
    );
  }

  const floors = building.floors || [];

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50">
      <div className="sticky top-0 z-30 bg-slate-800 px-4 py-3 flex items-center gap-3">
        <button onClick={handleBack} className="text-white hover:text-amber-300 transition-colors" aria-label="חזרה">
          <ArrowRight className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-white font-bold text-lg truncate leading-tight">
            {building.name}
            {building.code && <span className="text-slate-400 font-normal text-sm mr-2">({building.code})</span>}
          </h1>
          {projectName && (
            <p className="text-slate-300 text-xs truncate">{projectName}</p>
          )}
        </div>
      </div>

      <div className="sticky top-[52px] z-20 bg-white border-b border-slate-200 flex">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={`flex-1 py-3 text-sm font-medium text-center transition-colors border-b-2 ${
              activeTab === tab.id
                ? 'text-amber-600 border-amber-500'
                : 'text-slate-500 border-transparent hover:text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'units' && (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <Card className="p-3 text-center">
              <Layers className="w-5 h-5 text-blue-500 mx-auto mb-1" />
              <p className="text-xl font-bold text-slate-800">{kpis.floors}</p>
              <p className="text-[11px] text-slate-500">קומות</p>
            </Card>
            <Card className="p-3 text-center">
              <Home className="w-5 h-5 text-green-500 mx-auto mb-1" />
              <p className="text-xl font-bold text-slate-800">{kpis.units}</p>
              <p className="text-[11px] text-slate-500">דירות</p>
            </Card>
            <Card className="p-3 text-center">
              <AlertTriangle className="w-5 h-5 text-red-500 mx-auto mb-1" />
              <p className="text-xl font-bold text-slate-800">{kpis.openDefects}</p>
              <p className="text-[11px] text-slate-500">ליקויים פתוחים</p>
            </Card>
          </div>

          {floors.length === 0 ? (
            <Card className="p-6 text-center">
              <Layers className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">אין קומות בבניין זה</p>
            </Card>
          ) : (
            <div className="space-y-2">
              {floors.map(floor => {
                const isExpanded = expandedFloors[floor.id];
                const units = floor.units || [];
                const floorOpenDefects = floorDefectMap[floor.id] || 0;

                return (
                  <Card key={floor.id} className="overflow-hidden rounded-xl border-slate-200">
                    <button
                      onClick={() => toggleFloor(floor.id)}
                      className="w-full flex items-center gap-3 p-3.5 hover:bg-slate-50 transition-colors text-right"
                      aria-expanded={isExpanded}
                      aria-label={`${floor.display_label || floor.name} - ${units.length} דירות`}
                    >
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                        : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                      }
                      <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Layers className="w-4 h-4 text-blue-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-slate-800 truncate">
                          {floor.display_label || floor.name}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {units.length} דירות
                          {floorOpenDefects > 0 && (
                            <span className="text-red-500 font-medium mr-2">
                              · {floorOpenDefects} ליקויים
                            </span>
                          )}
                        </p>
                      </div>
                    </button>
                    {isExpanded && (
                      <div className="border-t border-slate-100 p-3">
                        {units.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-2">אין דירות בקומה זו</p>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {units.map(unit => {
                              const label = formatUnitLabel(unit.effective_label || unit.unit_no);
                              const defects = unitDefectMap[unit.id];
                              const openCount = defects?.open || 0;

                              return (
                                <button
                                  key={unit.id}
                                  onClick={() => navigate(`/projects/${projectId}/units/${unit.id}`)}
                                  className="relative flex items-center gap-1.5 bg-green-50 border border-green-200 rounded-lg px-3 py-2 hover:bg-green-100 hover:border-green-300 active:bg-green-200 transition-colors"
                                >
                                  <Home className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                                  <span className="text-xs font-medium text-green-700">{label}</span>
                                  {openCount > 0 && (
                                    <span className="absolute -top-1.5 -left-1.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
                                      {openCount}
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default InnerBuildingPage;
