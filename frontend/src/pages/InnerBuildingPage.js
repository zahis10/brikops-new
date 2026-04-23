import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, buildingService, floorService } from '../services/api';
import { formatUnitLabel } from '../utils/formatters';
import { Card } from '../components/ui/card';
import { toast } from 'sonner';
import {
  ArrowRight, Loader2, Building2, Layers, Home,
  ChevronDown, ChevronRight, AlertTriangle, WifiOff, Plus, X,
  Tag, Pencil
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

import UnitTypeEditModal, { UNIT_TYPE_TAGS, TAG_MAP } from '../components/UnitTypeEditModal';

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

  const [fabOpen, setFabOpen] = useState(false);
  const [addingFloor, setAddingFloor] = useState(false);
  const [newFloorName, setNewFloorName] = useState('');
  const [newFloorUnitCount, setNewFloorUnitCount] = useState('0');
  const [floorSaving, setFloorSaving] = useState(false);
  const [addingUnitToFloor, setAddingUnitToFloor] = useState(null);
  const [newUnitsCount, setNewUnitsCount] = useState('');
  const [unitSaving, setUnitSaving] = useState(false);
  const [pendingExpandFloor, setPendingExpandFloor] = useState(null);
  const [unitTypeFilter, setUnitTypeFilter] = useState(null);
  const [editingUnit, setEditingUnit] = useState(null);

  const addFloorFormRef = useRef(null);
  const floorRefs = useRef({});

  const handleBack = useCallback(() => {
    navigate(`/projects/${projectId}/control?tab=structure`);
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

  useEffect(() => {
    if (pendingExpandFloor && building) {
      const floors = building.floors || [];
      const target = floors.find(f => f.id === pendingExpandFloor) || floors.find(f => f.name === pendingExpandFloor) || floors[floors.length - 1];
      if (target) {
        setExpandedFloors(prev => ({ ...prev, [target.id]: true }));
        setTimeout(() => {
          const el = floorRefs.current[target.id];
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
      }
      setPendingExpandFloor(null);
    }
  }, [pendingExpandFloor, building]);

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
      navigate(`/projects/${projectId}/buildings/${buildingId}/qc`);
      return;
    }
    setActiveTab(tabId);
  };

  const toggleFloor = (floorId) => {
    setExpandedFloors(prev => ({ ...prev, [floorId]: !prev[floorId] }));
  };

  const handleAddFloor = async () => {
    if (!newFloorName.trim()) {
      toast.error('יש להזין קומה (מספר או שם)');
      return;
    }
    setFloorSaving(true);
    try {
      const unitCount = parseInt(newFloorUnitCount) || 0;
      const created = await buildingService.createFloor(buildingId, {
        name: newFloorName.trim(),
        floor_number: 0,
        unit_count: unitCount,
      });
      toast.success('קומה נוספה בהצלחה');
      const createdFloorId = created?.id || created?._id || newFloorName.trim();
      setAddingFloor(false);
      setNewFloorName('');
      setNewFloorUnitCount('0');
      setPendingExpandFloor(createdFloorId);
      await loadData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'שגיאה בהוספת קומה';
      toast.error(msg);
    } finally {
      setFloorSaving(false);
    }
  };

  const handleAddUnit = async (floorId) => {
    const count = parseInt(newUnitsCount) || 0;
    if (count <= 0) {
      toast.error('יש להזין כמות דירות (מספר חיובי)');
      return;
    }
    setUnitSaving(true);
    try {
      await floorService.createUnit(floorId, { unit_count: count });
      toast.success(`${count} דירות נוספו בהצלחה`);
      setAddingUnitToFloor(null);
      setNewUnitsCount('');
      await loadData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'שגיאה בהוספת דירות';
      toast.error(msg);
    } finally {
      setUnitSaving(false);
    }
  };

  const handleFabAddUnits = () => {
    setFabOpen(false);
    const expandedId = Object.keys(expandedFloors).find(id => expandedFloors[id]);
    if (expandedId) {
      setAddingUnitToFloor(expandedId);
      setNewUnitsCount('');
    } else {
      toast.info('בחר קומה תחילה');
    }
  };

  const handleFloorPlusClick = (e, floorId) => {
    e.stopPropagation();
    setAddingUnitToFloor(floorId);
    setNewUnitsCount('');
    if (!expandedFloors[floorId]) {
      setExpandedFloors(prev => ({ ...prev, [floorId]: true }));
    }
  };

  const openEditUnit = (e, unit) => {
    e.stopPropagation();
    setEditingUnit(unit);
  };

  const handleUnitSaved = ({ unitId, unit_type_tag, unit_note }) => {
    setBuilding(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        floors: (prev.floors || []).map(f => ({
          ...f,
          units: (f.units || []).map(u =>
            u.id === unitId ? { ...u, unit_type_tag, unit_note } : u
          ),
        })),
      };
    });
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
    <div dir="rtl" className="min-h-screen bg-slate-50" style={{ paddingBottom: 'calc(6rem + env(safe-area-inset-bottom, 0px))' }}>
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

          {addingFloor && (
            <Card ref={addFloorFormRef} className="p-3 bg-amber-50 border-amber-100 rounded-xl">
              <p className="text-xs font-medium text-amber-700 mb-2">הוסף קומה ל{building.name}</p>
              <div className="flex gap-2 items-start flex-wrap">
                <div className="flex-1 min-w-[120px]">
                  <label htmlFor="add-floor-name" className="block text-[11px] font-medium text-amber-800 mb-1">שם/מספר קומה</label>
                  <input
                    id="add-floor-name"
                    type="text"
                    value={newFloorName}
                    onChange={e => setNewFloorName(e.target.value)}
                    placeholder="למשל: 1, -1, גג"
                    className="w-full text-sm border border-amber-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
                    onKeyDown={e => e.key === 'Enter' && handleAddFloor()}
                    autoFocus
                  />
                </div>
                <div className="w-28">
                  <label htmlFor="add-floor-units" className="block text-[11px] font-medium text-amber-800 mb-1">מס׳ דירות בקומה</label>
                  <input
                    id="add-floor-units"
                    type="number"
                    min="0"
                    value={newFloorUnitCount}
                    onChange={e => setNewFloorUnitCount(e.target.value)}
                    placeholder="0"
                    className="w-full text-sm border border-amber-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400 text-center"
                    onKeyDown={e => e.key === 'Enter' && handleAddFloor()}
                  />
                </div>
                <button
                  onClick={handleAddFloor}
                  disabled={floorSaving}
                  className="bg-amber-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 flex-shrink-0 mt-[18px]"
                >
                  {floorSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'הוסף'}
                </button>
                <button
                  onClick={() => { setAddingFloor(false); setNewFloorName(''); setNewFloorUnitCount('0'); }}
                  className="text-slate-400 hover:text-slate-600 flex-shrink-0 mt-[18px]"
                  aria-label="ביטול"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </Card>
          )}

          <div className="flex gap-1.5 mb-3 flex-wrap">
            <button
              onClick={() => setUnitTypeFilter(null)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!unitTypeFilter ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >הכל</button>
            {UNIT_TYPE_TAGS.map(t => (
              <button
                key={t.value}
                onClick={() => setUnitTypeFilter(unitTypeFilter === t.value ? null : t.value)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${unitTypeFilter === t.value ? 'bg-slate-700 text-white' : t.color + ' hover:opacity-80'}`}
              >{t.label}</button>
            ))}
          </div>

          {floors.length === 0 && !addingFloor ? (
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
                  <Card
                    key={floor.id}
                    ref={el => { floorRefs.current[floor.id] = el; }}
                    className="overflow-hidden rounded-xl border-slate-200"
                  >
                    <div className="flex items-center">
                      <button
                        onClick={() => toggleFloor(floor.id)}
                        className="flex-1 flex items-center gap-3 p-3.5 hover:bg-slate-50 transition-colors text-right"
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
                      <button
                        onClick={(e) => handleFloorPlusClick(e, floor.id)}
                        className="p-2 ml-1 text-blue-500 hover:bg-blue-50 rounded-md transition-colors flex-shrink-0"
                        aria-label="הוסף דירות"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="border-t border-slate-100 p-3">
                        {addingUnitToFloor === floor.id && (
                          <div className="flex gap-2 items-center mb-2 bg-blue-50 p-2 rounded-lg">
                            <input
                              type="number"
                              min="1"
                              value={newUnitsCount}
                              onChange={e => setNewUnitsCount(e.target.value)}
                              placeholder="כמות דירות"
                              aria-label="כמות דירות להוספה"
                              className="flex-1 text-sm border border-blue-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                              onKeyDown={e => e.key === 'Enter' && handleAddUnit(floor.id)}
                              autoFocus
                            />
                            <button
                              onClick={() => handleAddUnit(floor.id)}
                              disabled={unitSaving}
                              className="bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
                            >
                              {unitSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'הוסף'}
                            </button>
                            <button
                              onClick={() => { setAddingUnitToFloor(null); setNewUnitsCount(''); }}
                              className="text-slate-400 hover:text-slate-600"
                              aria-label="ביטול"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                        {(() => {
                          const filtered = unitTypeFilter ? units.filter(u => u.unit_type_tag === unitTypeFilter) : units;
                          return filtered.length === 0 && addingUnitToFloor !== floor.id ? (
                            <p className="text-xs text-slate-400 text-center py-2">{unitTypeFilter ? 'אין דירות מסוג זה בקומה' : 'אין דירות בקומה זו'}</p>
                          ) : filtered.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {filtered.map(unit => {
                                const label = formatUnitLabel(unit.effective_label || unit.unit_no);
                                const defects = unitDefectMap[unit.id];
                                const openCount = defects?.open || 0;
                                const tagInfo = TAG_MAP[unit.unit_type_tag];

                                return (
                                  <button
                                    key={unit.id}
                                    onClick={() => navigate(`/projects/${projectId}/units/${unit.id}`)}
                                    className="relative flex flex-col items-start bg-green-50 border border-green-200 rounded-lg px-3 py-2 hover:bg-green-100 hover:border-green-300 active:bg-green-200 transition-colors min-w-[80px] group"
                                  >
                                    <div className="flex items-center gap-1.5 w-full">
                                      <Home className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                                      <span className="text-xs font-medium text-green-700">{label}</span>
                                      <span
                                        onClick={(e) => openEditUnit(e, unit)}
                                        className="unit-edit-icon mr-auto text-slate-400 hover:text-blue-500 transition-opacity"
                                      >
                                        <Pencil className="w-3 h-3" />
                                      </span>
                                    </div>
                                    {tagInfo && (
                                      <span className={`mt-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${tagInfo.color}`}>
                                        {tagInfo.label}
                                      </span>
                                    )}
                                    {unit.unit_note && (
                                      <span className="mt-0.5 text-[10px] text-slate-400 truncate max-w-[120px]">{unit.unit_note}</span>
                                    )}
                                    {openCount > 0 && (
                                      <span className="absolute -top-1.5 -start-1.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
                                        {openCount}
                                      </span>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          ) : null;
                        })()}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'units' && (
        <>
          {fabOpen && (
            <div
              className="fixed inset-0 bg-black/20 z-30"
              onClick={() => setFabOpen(false)}
            />
          )}
          <div className="fixed left-4 z-40 flex flex-col items-center gap-2" style={{ bottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))' }}>
            {fabOpen && (
              <>
                <button
                  onClick={() => { setFabOpen(false); setAddingFloor(true); setNewFloorName(''); setNewFloorUnitCount('0'); }}
                  className="flex items-center gap-2 bg-white shadow-lg rounded-full px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors border border-slate-200"
                >
                  <Layers className="w-4 h-4 text-amber-500" />
                  הוסף קומה
                </button>
                <button
                  onClick={handleFabAddUnits}
                  className="flex items-center gap-2 bg-white shadow-lg rounded-full px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors border border-slate-200"
                >
                  <Home className="w-4 h-4 text-blue-500" />
                  הוסף דירות
                </button>
              </>
            )}
            <button
              onClick={() => setFabOpen(prev => !prev)}
              className="w-14 h-14 rounded-full bg-amber-500 text-white shadow-lg hover:bg-amber-600 active:bg-amber-700 transition-all flex items-center justify-center"
              aria-label={fabOpen ? 'סגור תפריט' : 'פתח תפריט הוספה'}
            >
              <Plus
                className="w-6 h-6 transition-transform duration-200"
                style={{ transform: `rotate(${fabOpen ? 45 : 0}deg)` }}
              />
            </button>
          </div>
        </>
      )}

      {editingUnit && (
        <UnitTypeEditModal
          unit={editingUnit}
          onClose={() => setEditingUnit(null)}
          onSaved={handleUnitSaved}
        />
      )}
    </div>
  );
};

export default InnerBuildingPage;
