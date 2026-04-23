import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { buildingService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import ExportModal from '../components/ExportModal';
import { formatUnitLabel } from '../utils/formatters';
import { tCategory } from '../i18n';
import { toast } from 'sonner';
import FilterDrawer from '../components/FilterDrawer';
import OfflineState from '../components/OfflineState';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import { arraysEqualAsSets } from '../utils/filterHelpers';
import {
  ArrowRight, Loader2, Building2, ChevronDown, ChevronUp,
  Home, AlertTriangle, Clock, CheckCircle2, SlidersHorizontal, Search, X, Download, Pencil
} from 'lucide-react';

const BUILDING_DEFAULT_FILTERS = {
  status: [],
  category: [],
  floor: [],
  unit: [],
};

const STATUS_FILTER_OPTIONS = [
  { value: 'open', label: 'פתוחים' },
  { value: 'closed', label: 'סגורים' },
  { value: 'blocking', label: 'חוסמי מסירה' },
];

const STATUS_LABEL_MAP = {
  open: 'פתוחים',
  closed: 'סגורים',
  blocking: 'חוסמי מסירה',
};

const BUILDING_PRESETS = [
  { id: 'open', label: 'פתוחים', values: { status: ['open'] } },
  { id: 'blocking', label: 'חוסמים', values: { status: ['blocking'] } },
  { id: 'open_blocking', label: 'פתוחים + חוסמים', values: { status: ['open', 'blocking'] } },
  { id: 'closed', label: 'סגורים', values: { status: ['closed'] } },
];

const getBuildingActivePresetId = (draft) => {
  if (
    draft.category.length > 0 ||
    draft.floor.length > 0 ||
    draft.unit.length > 0
  ) return null;
  for (const p of BUILDING_PRESETS) {
    if (arraysEqualAsSets(draft.status, p.values.status)) return p.id;
  }
  return null;
};

import UnitTypeEditModal, { UNIT_TYPE_TAGS, TAG_MAP } from '../components/UnitTypeEditModal';

const BuildingDefectsPage = () => {
  const { projectId, buildingId } = useParams();
  const navigate = useNavigate();
  const { features } = useAuth();

  const online = useOnlineStatus();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const flagChecked = !!features?.defects_v2;
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [filters, setFilters] = useState({ ...BUILDING_DEFAULT_FILTERS });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [expandedFloors, setExpandedFloors] = useState({});
  const [unitTypeFilter, setUnitTypeFilter] = useState(null);
  const [editingUnit, setEditingUnit] = useState(null);

  useEffect(() => {
    if (features && !features.defects_v2) {
      navigate(`/projects/${projectId}/control?tab=defects`, { replace: true });
    }
  }, [features, projectId, navigate]);

  const loadData = useCallback(async () => {
    if (!flagChecked) return;
    setLoading(true);
    try {
      const result = await buildingService.defectsSummary(buildingId);
      setData(result);
      const allFloors = {};
      (result.floors || []).forEach((_, i) => { allFloors[i] = true; });
      setExpandedFloors(allFloors);
    } catch (err) {
      console.error('Failed to load building defects summary:', err);
      if (err?.response?.status === 403) {
        toast.error('אין לך הרשאה לצפות בנתוני בניין זה');
        navigate(`/projects/${projectId}/control?tab=defects`);
        return;
      }
      toast.error('שגיאה בטעינת סיכום ליקויים');
    } finally {
      setLoading(false);
    }
  }, [buildingId, projectId, navigate, flagChecked]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!data?.floors) return;
    setFilters(prev => {
      const next = { ...prev };
      let changed = false;
      if (prev.floor.length > 0) {
        const validFloorIds = new Set(data.floors.map(f => f.id));
        const filtered = prev.floor.filter(id => validFloorIds.has(id));
        if (filtered.length !== prev.floor.length) {
          next.floor = filtered;
          changed = true;
        }
      }
      if (prev.unit.length > 0) {
        const allUnitIds = new Set(data.floors.flatMap(f => (f.units || []).map(u => u.id)));
        const filtered = prev.unit.filter(id => allUnitIds.has(id));
        if (filtered.length !== prev.unit.length) {
          next.unit = filtered;
          changed = true;
        }
      }
      if (prev.category.length > 0) {
        const allCats = new Set();
        data.floors.forEach(f => (f.units || []).forEach(u => (u.categories || []).forEach(c => allCats.add(c))));
        const filtered = prev.category.filter(c => allCats.has(c));
        if (filtered.length !== prev.category.length) {
          next.category = filtered;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [data]);

  const toggleFloor = (idx) => {
    setExpandedFloors(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const openEditUnit = (e, unit) => {
    e.stopPropagation();
    setEditingUnit(unit);
  };

  const handleUnitSaved = ({ unitId, unit_type_tag, unit_note }) => {
    setData(prev => {
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

  const getUnitBadgeColor = (unit) => {
    const open = (unit.defect_counts?.open || 0) + (unit.defect_counts?.in_progress || 0);
    if (open >= 3) return 'bg-red-500 text-white';
    if (open >= 1) return 'bg-amber-500 text-white';
    if ((unit.defect_counts?.total || 0) > 0) return 'bg-green-500 text-white';
    return 'bg-slate-200 text-slate-500';
  };

  const getUnitIconColor = (unit) => {
    const open = (unit.defect_counts?.open || 0) + (unit.defect_counts?.in_progress || 0);
    if (open >= 3) return 'text-red-500';
    if (open >= 1) return 'text-amber-500';
    if ((unit.defect_counts?.total || 0) > 0) return 'text-green-500';
    return 'text-slate-300';
  };

  const unitPassesFilter = (unit) => {
    if (unitTypeFilter && unit.unit_type_tag !== unitTypeFilter) return false;
    if (filters.unit.length > 0 && !filters.unit.includes(unit.id)) return false;
    if (filters.category.length > 0) {
      const unitCats = unit.categories || [];
      if (!filters.category.some(c => unitCats.includes(c))) return false;
    }
    if (filters.status.length > 0) {
      const c = unit.defect_counts || {};
      const matchesAny =
        (filters.status.includes('open')     && ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0)) > 0) ||
        (filters.status.includes('closed')   && (c.closed || 0) > 0) ||
        (filters.status.includes('blocking') && ((c.open || 0) + (c.in_progress || 0)) > 0);
      if (!matchesAny) return false;
    }
    const searchLower = searchQuery.trim().toLowerCase();
    if (searchLower) {
      const label = (unit.display_label || unit.unit_no || '').toLowerCase();
      if (!label.includes(searchLower)) return false;
    }
    return true;
  };

  const getStatusCount = (c) => {
    if (!c) return 0;
    if (filters.status.length === 1) {
      const s = filters.status[0];
      if (s === 'open') return (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0);
      if (s === 'closed') return c.closed || 0;
      if (s === 'blocking') return (c.open || 0) + (c.in_progress || 0);
    }
    if (filters.status.length > 1) {
      let sum = 0;
      if (filters.status.includes('open'))     sum += (c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0);
      if (filters.status.includes('closed'))   sum += (c.closed || 0);
      if (filters.status.includes('blocking')) sum += (c.open || 0) + (c.in_progress || 0);
      return sum;
    }
    return c.total || 0;
  };

  const getFilteredFloorData = () => {
    if (!data?.floors) return [];
    const hasFilters = filters.status.length > 0 || filters.category.length > 0 || filters.floor.length > 0 || filters.unit.length > 0 || searchQuery.trim();
    return (data.floors || [])
      .filter(f => filters.floor.length === 0 || filters.floor.includes(f.id))
      .map(floor => {
        const filteredUnits = (floor.units || []).filter(unitPassesFilter);
        return { ...floor, filteredUnits };
      })
      .filter(floor => !hasFilters || floor.filteredUnits.length > 0);
  };

  const getFloorDefectCount = (filteredUnits) => {
    return filteredUnits.reduce((sum, u) => sum + getStatusCount(u.defect_counts), 0);
  };

  const filterSections = useMemo(() => {
    if (!data?.floors) return [];
    const cats = new Set();
    const catCounts = {};
    const statusCounts = { open: 0, closed: 0, blocking: 0 };
    const floorOpts = [];
    const unitOpts = [];

    (data.floors || []).forEach(f => {
      const fUnits = f.units || [];
      floorOpts.push({
        value: f.id,
        label: f.display_label || f.name || `קומה ${f.floor_number}`,
        count: fUnits.length,
      });
      fUnits.forEach(u => {
        (u.categories || []).forEach(c => {
          cats.add(c);
          catCounts[c] = (catCounts[c] || 0) + 1;
        });
        const c = u.defect_counts || {};
        if ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0) > 0) statusCounts.open += 1;
        if ((c.closed || 0) > 0) statusCounts.closed += 1;
        if ((c.open || 0) + (c.in_progress || 0) > 0) statusCounts.blocking += 1;
        unitOpts.push({
          value: u.id,
          label: formatUnitLabel(u.display_label || u.unit_no || ''),
          count: c.total || 0,
        });
      });
    });

    return [
      {
        key: 'status',
        label: 'סטטוס',
        options: STATUS_FILTER_OPTIONS.map(o => ({ ...o, count: statusCounts[o.value] || 0 })),
      },
      {
        key: 'category',
        label: 'תחום',
        options: [...cats].sort().map(c => ({ value: c, label: tCategory(c), count: catCounts[c] || 0 })),
      },
      { key: 'floor', label: 'קומה', options: floorOpts },
      { key: 'unit', label: 'דירה', options: unitOpts },
    ];
  }, [data]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.status.length > 0) count++;
    if (filters.category.length > 0) count++;
    if (filters.floor.length > 0) count++;
    if (filters.unit.length > 0) count++;
    if (searchQuery.trim()) count++;
    return count;
  }, [filters, searchQuery]);

  const filterSummaryText = useMemo(() => {
    const parts = [];
    filterSections.forEach(section => {
      const vals = filters[section.key];
      if (Array.isArray(vals) && vals.length > 0) {
        const labels = vals.map(v => section.options.find(o => o.value === v)?.label || v);
        const joined = labels.length === 1 ? labels[0] : `${labels[0]} +${labels.length - 1}`;
        parts.push(`${section.label}: ${joined}`);
      }
    });
    if (searchQuery.trim()) parts.push(`חיפוש: "${searchQuery.trim()}"`);
    if (parts.length === 0) return '';
    if (parts.length <= 3) return parts.join(' · ');
    return parts.slice(0, 2).join(' · ') + ` · עוד ${parts.length - 2}`;
  }, [filters, searchQuery, filterSections]);

  const computeMatchCount = useCallback((draft) => {
    if (!data?.floors) return 0;
    const draftSearchLower = searchQuery.trim().toLowerCase();
    const unitPasses = (unit) => {
      if (unitTypeFilter && unit.unit_type_tag !== unitTypeFilter) return false;
      if (draft.unit.length > 0 && !draft.unit.includes(unit.id)) return false;
      if (draft.category.length > 0) {
        const unitCats = unit.categories || [];
        if (!draft.category.some(c => unitCats.includes(c))) return false;
      }
      if (draft.status.length > 0) {
        const c = unit.defect_counts || {};
        const matchesAny =
          (draft.status.includes('open')     && ((c.open || 0) + (c.in_progress || 0) + (c.waiting_verify || 0)) > 0) ||
          (draft.status.includes('closed')   && (c.closed || 0) > 0) ||
          (draft.status.includes('blocking') && ((c.open || 0) + (c.in_progress || 0)) > 0);
        if (!matchesAny) return false;
      }
      if (draftSearchLower) {
        const label = (unit.display_label || unit.unit_no || '').toLowerCase();
        if (!label.includes(draftSearchLower)) return false;
      }
      return true;
    };
    let count = 0;
    (data.floors || [])
      .filter(f => draft.floor.length === 0 || draft.floor.includes(f.id))
      .forEach(f => {
        count += (f.units || []).filter(unitPasses).length;
      });
    return count;
  }, [data, searchQuery, unitTypeFilter]);

  const hasActiveFilters = activeFilterCount > 0;

  const getTotalCounts = () => {
    if (!data?.floors) return { total: 0, pending: 0, followUp: 0 };
    let total = 0, pending = 0, followUp = 0;
    data.floors.forEach(floor => {
      (floor.units || []).forEach(u => {
        const c = u.defect_counts || {};
        total += c.total || 0;
        pending += (c.open || 0) + (c.in_progress || 0);
        followUp += c.waiting_verify || 0;
      });
    });
    return { total, pending, followUp };
  };

  if (!online && !data) {
    return <OfflineState onRetry={loadData} />;
  }

  if (!flagChecked || (loading && !data)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-10 h-10 text-amber-500 animate-spin mx-auto" />
          <p className="text-slate-500 mt-4 text-sm">טוען סיכום ליקויים...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <Building2 className="w-12 h-12 text-slate-300" />
        <p className="text-slate-500">לא נמצאו נתונים לבניין זה</p>
        <button onClick={() => navigate(`/projects/${projectId}/control?tab=defects`)} className="text-amber-600 hover:text-amber-700 font-medium text-sm">
          חזרה לליקויים
        </button>
      </div>
    );
  }

  const counts = getTotalCounts();
  const filteredFloors = getFilteredFloorData();

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-slate-50">
        <div className="max-w-lg mx-auto bg-gradient-to-l from-amber-500 to-amber-600 text-white rounded-b-2xl px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/control?tab=structure`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-amber-200" />
                <h1 className="text-lg font-bold truncate">{data.building?.name || 'בניין'}</h1>
              </div>
              <p className="text-xs text-amber-100 mt-0.5">
                {data.project?.name || ''} • סיכום ליקויים
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-2 space-y-3">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button
            onClick={() => setSummaryOpen(!summaryOpen)}
            className="w-full flex items-center justify-between p-3 text-right"
          >
            <span className="text-sm font-semibold text-slate-700">סיכום מהיר</span>
            {summaryOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {summaryOpen && (
            <div className="px-3 pb-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-slate-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-slate-800">{counts.total}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">סה״כ</div>
                </div>
                <div className="bg-red-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-red-600">{counts.pending}</div>
                  <div className="text-[10px] text-red-500 mt-0.5">ממתינים</div>
                </div>
                <div className="bg-amber-50 rounded-lg p-2.5 text-center">
                  <div className="text-xl font-bold text-amber-600">{counts.followUp}</div>
                  <div className="text-[10px] text-amber-500 mt-0.5">לאימות</div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="חפש לפי מספר דירה..."
                className="w-full pr-9 pl-3 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-amber-400"
              />
            </div>
            <button
              type="button"
              onClick={() => setFilterDrawerOpen(true)}
              className="relative px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center gap-1.5 text-sm font-medium text-slate-600"
            >
              <SlidersHorizontal className="w-4 h-4" />
              סינון
              {activeFilterCount > 0 && (
                <span className="absolute -top-1.5 -start-1.5 min-w-[18px] h-[18px] bg-amber-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setExportModalOpen(true)}
              className="px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center gap-1.5 text-sm font-medium text-slate-600"
            >
              <Download className="w-4 h-4" />
              ייצוא
            </button>
          </div>

          {hasActiveFilters && filterSummaryText && (
            <div className="flex items-center gap-2 text-xs text-slate-500 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
              <span className="flex-1 truncate">{filterSummaryText}</span>
              <button
                type="button"
                onClick={() => { setFilters({ ...BUILDING_DEFAULT_FILTERS }); setSearchQuery(''); }}
                className="text-amber-600 hover:text-amber-700 flex-shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

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

        <div className="space-y-2 pb-6">
          {filteredFloors.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">
                {hasActiveFilters ? 'אין קומות התואמות לסינון' : 'אין קומות בבניין זה'}
              </p>
            </div>
          ) : (
            filteredFloors.map((floor, idx) => {
              const originalIdx = (data.floors || []).findIndex(f => f.id === floor.id);
              const floorCount = getFloorDefectCount(floor.filteredUnits);
              const isExpanded = expandedFloors[originalIdx];

              return (
                <div key={floor.id || idx} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                  <button
                    onClick={() => toggleFloor(originalIdx)}
                    className="w-full flex items-center gap-3 p-3 text-right hover:bg-slate-50 transition-colors"
                  >
                    <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                      <span className="text-sm font-bold text-amber-700">{floor.name || floor.floor_number || idx}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-semibold text-slate-800">
                        {floor.display_label || floor.name || `קומה ${floor.floor_number ?? idx}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {floorCount > 0 && (
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                          filters.status.includes('blocking') ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {floorCount}
                        </span>
                      )}
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-3 pb-3 border-t border-slate-100">
                      {floor.filteredUnits.length === 0 ? (
                        <p className="text-xs text-slate-400 text-center py-3">{unitTypeFilter ? 'אין דירות מסוג זה בקומה' : 'אין דירות בקומה זו'}</p>
                      ) : (
                        <div className="grid grid-cols-4 sm:grid-cols-5 gap-2 pt-3">
                          {floor.filteredUnits.map(unit => {
                            const badgeCount = getStatusCount(unit.defect_counts);
                            const tagInfo = TAG_MAP[unit.unit_type_tag];

                            return (
                              <div key={unit.id} className="flex flex-col items-center gap-1 p-2 rounded-xl hover:bg-slate-50 transition-colors group relative">
                                <button
                                  onClick={() => navigate(`/projects/${projectId}/units/${unit.id}/defects`, { state: { from: 'building-defects', buildingId } })}
                                  className="flex flex-col items-center gap-1 active:scale-95"
                                >
                                  <div className="relative">
                                    <Home className={`w-8 h-8 ${getUnitIconColor(unit)}`} />
                                    {badgeCount > 0 && (
                                      <span className={`absolute -top-1.5 -start-1.5 text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center ${getUnitBadgeColor(unit)}`}>
                                        {badgeCount}
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-[11px] text-slate-600 font-medium truncate max-w-full">
                                    {formatUnitLabel(unit.display_label || unit.unit_no || '')}
                                  </span>
                                  {tagInfo && (
                                    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${tagInfo.color}`}>
                                      {tagInfo.label}
                                    </span>
                                  )}
                                  {unit.unit_note && (
                                    <span className="text-[9px] text-slate-400 truncate max-w-[80px]">{unit.unit_note}</span>
                                  )}
                                </button>
                                <span
                                  onClick={(e) => openEditUnit(e, unit)}
                                  className="unit-edit-icon absolute top-1 left-1 text-slate-400 hover:text-blue-500 cursor-pointer transition-opacity"
                                >
                                  <Pencil className="w-3 h-3" />
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      <FilterDrawer
        open={filterDrawerOpen}
        onOpenChange={setFilterDrawerOpen}
        filters={filters}
        defaultFilters={BUILDING_DEFAULT_FILTERS}
        onApply={setFilters}
        sections={filterSections}
        computeMatchCount={computeMatchCount}
        matchLabel="דירות"
        presets={BUILDING_PRESETS}
        getActivePresetId={getBuildingActivePresetId}
      />

      <ExportModal
        open={exportModalOpen}
        onOpenChange={setExportModalOpen}
        scope="building"
        buildingId={buildingId}
        filters={{
          status: filters.status.length === 1 ? filters.status[0] : 'all',
          category: filters.category.length === 1 ? filters.category[0] : 'all',
          floor: filters.floor.length === 1 ? filters.floor[0] : 'all',
          unit: filters.unit.length === 1 ? filters.unit[0] : 'all',
          search: searchQuery,
        }}
        meta={{
          projectName: data?.project?.name,
          buildingName: data?.building?.name,
        }}
      />

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

export default BuildingDefectsPage;
